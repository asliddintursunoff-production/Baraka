"""Tool registry: ONE set for chat and Live (spec §5.4).

Each tool: name, Uzbek description, JSON schema, handler. Every response has the same
envelope (`ok, verdict, facts, display, speech, say, ui_blocks, answer, proposed_plan,
insufficient_data`). Numbers come only from the engine; `display`/`speech`/`say` are
built by `uz_format`. `business_id` is never an argument: it comes from the context.
`for_model()` strips the UI blocks and keeps the envelope <= 2 KB.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Min, Sum

from apps.actions.models import ActionPlan
from apps.engine import (
    Change,
    EngineError,
    ForecastResult,
    StaffCountUnknown,
    evaluate_purchase,
    explain_day,
    simulate,
    spend_limit_until,
)
from apps.finance.models import Transaction
from apps.insights import advice
from apps.insights.forecasting import CachedForecast, refresh_forecast
from apps.insights.forecasting import get_forecast as load_forecast
from apps.tenancy.models import Business

from . import uz_format as uz

MLN = Decimal(1_000_000)
AFFIRMATIVE = re.compile(
    r"^\s*(ha|xa|xo'?p|mayli|roziman|tasdiqlayman|bo'?pti|albatta|ok|okay|да|ага|конечно)\b",
    re.IGNORECASE,
)

PAY_PHRASE = {
    "payroll": "xodimlarga oylik berishga",
    "loan": "kredit to'lashga",
    "rent": "ijara to'lashga",
    "tax": "soliq to'lashga",
}
PAY_DAY = {
    "payroll": "oylik kuni",
    "loan": "kredit kuni",
    "rent": "ijara kuni",
    "tax": "soliq kuni",
}


class ToolArgError(ValueError):
    pass


@dataclass
class ToolContext:
    business: Business
    user_id: int | None
    channel: str  # chat | voice | api
    last_user_text: str = ""
    _cached: CachedForecast | None = None
    _history_months: int | None = None

    @property
    def cached(self) -> CachedForecast:
        if self._cached is None:
            self._cached = load_forecast(self.business)
        return self._cached

    @property
    def base(self) -> ForecastResult:
        return self.cached.result

    @property
    def short_history(self) -> bool:
        """Under MIN_HISTORY_DAYS of real data: no forecasts or purchase decisions."""
        from apps.tenancy.gate import history_days

        if self.business.is_demo:
            return self.base.insufficient_data
        from config import app_settings as cfg

        return self.base.insufficient_data or history_days(self.business) < cfg.MIN_HISTORY_DAYS

    def history_months(self) -> int:
        if self._history_months is None:
            first = Transaction.objects.aggregate(m=Min("txn_date"))["m"]
            days = (self.base.today - first).days if first else 0
            self._history_months = max(0, round(days / 30))
        return self._history_months


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]
    voice: bool = True  # offered to the Live model
    spec_extra: dict[str, Any] = field(default_factory=dict)

    def declaration(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


# --- tiny JSON-schema subset validator -----------------------------------------------
def validate(schema: dict[str, Any], args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        raise ToolArgError("arguments must be an object")
    props: dict[str, Any] = schema.get("properties", {})
    unknown = set(args) - set(props)
    if unknown:
        raise ToolArgError(f"unknown arguments: {sorted(unknown)}")
    for req in schema.get("required", []):
        if args.get(req) in (None, ""):
            raise ToolArgError(f"{req} is required")
    out: dict[str, Any] = {}
    for key, rule in props.items():
        if key not in args or args[key] is None:
            continue
        v = args[key]
        t = rule.get("type")
        if t == "integer":
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            if isinstance(v, str) and v.strip().isdigit():
                v = int(v.strip())
            if not isinstance(v, int) or isinstance(v, bool):
                raise ToolArgError(f"{key} must be an integer")
            if "minimum" in rule and v < rule["minimum"]:
                raise ToolArgError(f"{key} must be >= {rule['minimum']}")
            if "maximum" in rule and v > rule["maximum"]:
                raise ToolArgError(f"{key} must be <= {rule['maximum']}")
        elif t == "number":
            try:
                v = Decimal(str(v))
            except InvalidOperation as exc:
                raise ToolArgError(f"{key} must be a number") from exc
        elif t == "string":
            if not isinstance(v, str):
                raise ToolArgError(f"{key} must be a string")
            v = v.strip()[: rule.get("maxLength", 300)]
            if rule.get("format") == "date":
                try:
                    v = date.fromisoformat(v)
                except ValueError as exc:
                    raise ToolArgError(f"{key} must be a YYYY-MM-DD date") from exc
        if "enum" in rule and (v if not isinstance(v, Decimal) else int(v)) not in rule["enum"]:
            raise ToolArgError(f"{key} must be one of {rule['enum']}")
        out[key] = v
    return out


# --- envelope helpers -------------------------------------------------------------------
def envelope(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ok": True,
        "verdict": None,
        "facts": {},
        "display": {},
        "speech": {},
        "say": "",
        "ui_blocks": [],
        "answer": None,
        "proposed_plan": None,
        "insufficient_data": False,
    }
    base.update(kw)
    return base


def for_model(result: dict[str, Any]) -> dict[str, Any]:
    """What the LLM sees: no UI blocks, no long answer templates; <= 2 KB."""
    slim = {k: v for k, v in result.items() if k not in {"ui_blocks", "answer"}}
    raw = json.dumps(slim, ensure_ascii=False, default=str)
    if len(raw.encode()) > 2048:
        slim.pop("display", None)
        facts = slim.get("facts", {})
        if isinstance(facts, dict) and "payments" in facts:
            facts["payments"] = facts["payments"][:5]
    return slim


def money(v: Decimal) -> str:
    return f"{v:.2f}"


def insufficient() -> dict[str, Any]:
    text = "Ishonchli prognoz uchun kamida 2 haftalik ma'lumot kerak."
    return envelope(
        ok=True,
        insufficient_data=True,
        say=text,
        answer={
            "verdict": "info",
            "headline": "Ma'lumot yetarli emas",
            "reason": text,
            "steps": [],
        },
    )


def freshness_note(business: Business) -> str:
    """ "31-oktabr holati; 1–21-noyabr kunlik hisobotlari hali kiritilmagan" (stale data only)."""
    q = business.data_quality or {}
    return str(q.get("text") or "") if q.get("stale") and not business.is_demo else ""


def cash_prefix(business: Business) -> str:
    q = business.data_quality or {}
    if q.get("stale") and not business.is_demo and q.get("as_of"):
        return f"{uz.format_date(date.fromisoformat(q['as_of']))} holatiga kassada"
    return "Hozir kassada"


def explain_lines(ctx: ToolContext, *extra: str) -> list[str]:
    n_crit = sum(
        1
        for p in ctx.base.obligations
        if p.priority == "critical" and p.date <= ctx.base.today + timedelta(days=60)
    )
    lines = [
        f"Sizning {ctx.history_months()} oylik jadvalingiz va {n_crit} ta majburiy to'lov sanasi",
        "Har bir kunning qoldig'i alohida hisoblandi, AI raqamni o'zi o'ylab topmaydi",
    ]
    q = ctx.business.data_quality or {}
    if q.get("first_date") and q.get("last_date"):
        a, b = date.fromisoformat(q["first_date"]), date.fromisoformat(q["last_date"])
        lines.append(f"Ma'lumot davri: {uz.format_date(a)} – {uz.format_date(b)} {b.year}")
    if q.get("recon"):
        lines.append(
            "Faylning o'z hisobotlari (Pul oqimi, Foyda-zarar) bilan solishtirildi: "
            + ("hammasi mos ✓" if q.get("recon_ok") else "mos kelmagan oylar bor ✗")
        )
    if note := freshness_note(ctx.business):
        lines.append(note[0].upper() + note[1:])
    return lines + [e for e in extra if e]


def main_payment(base: ForecastResult, d: date) -> Any:
    pays = advice.payments_on(base, d)
    pays.sort(key=lambda p: (p.category != "payroll", p.priority != "critical"))
    return pays[0] if pays else None


def plan_key(business_id: int, kind: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f"ai:{business_id}:{kind}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def propose(
    ctx: ToolContext, kind: str, payload: dict[str, Any], due: date | None
) -> dict[str, Any]:
    """Create (or reuse) a PROPOSED plan. Never executes anything."""
    tz = ZoneInfo(ctx.business.timezone)
    due_at = datetime.combine(due, time(9, 0), tz) if due else None
    plan, _ = ActionPlan.objects.get_or_create(
        idempotency_key=plan_key(ctx.business.pk, kind, payload),
        defaults={
            "business": ctx.business,
            "kind": kind,
            "payload": payload,
            "status": ActionPlan.Status.PROPOSED,
            "proposed_by": "ai",
            "due_at": due_at,
        },
    )
    return {"id": plan.pk, "summary": plan.payload.get("summary", ""), "status": plan.status}


# --- tools --------------------------------------------------------------------------------
def cash_only(ctx: ToolContext) -> dict[str, Any]:
    """Short history: only current cash and the next payments, no forecast."""
    base = ctx.base
    cash = base.close_on(base.today)
    end = base.today + timedelta(days=30)
    pays = sorted(
        (o for o in base.obligations if base.today <= o.date <= end), key=lambda o: o.date
    )[:3]
    lines = "; ".join(
        f"{uz.format_date(o.date)} — {o.title} {uz.format_mln(o.amount)}" for o in pays
    )
    note = "Prognoz va xarid qarorlari uchun kamida 2 haftalik ma'lumot kerak."
    reason = (f"Kelgusi to'lovlar: {lines}. " if pays else "") + note
    return envelope(
        ok=True,
        insufficient_data=True,
        facts={
            "cash": money(cash),
            "payments": [
                {"date": o.date.isoformat(), "title": o.title, "amount": money(o.amount)}
                for o in pays
            ],
        },
        say=f"{cash_prefix(ctx.business)} {uz.speech_amount(cash)} bor. {note}",
        answer={
            "verdict": "info",
            "headline": f"{cash_prefix(ctx.business)} {uz.format_mln(cash)}",
            "reason": reason,
            "steps": [],
        },
    )


def get_cash_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = ctx.base
    if base.insufficient_data or ctx.short_history:
        return cash_only(ctx)
    cash = base.close_on(base.today)
    d, low = base.min_date, base.min_balance
    pays = advice.payments_on(base, d)
    words = advice.join_uz([advice.payment_word(p) for p in pays])
    s60 = advice.horizon_summary(base, 60)
    say = (
        f"{cash_prefix(ctx.business)} {uz.speech_amount(cash)} bor. "
        f"Eng qiyin kun {uz.uz_ordinal_date(d)}, o'shanda {uz.speech_amount(low)} qoladi."
    )
    headline = (
        "Pulingiz yetadi."
        if base.verdict == "yes"
        else "Ehtiyot bo'ling."
        if base.verdict == "risky"
        else "Pul yetmaydigan kun bor."
    )
    return envelope(
        verdict=base.verdict,
        facts={"cash_now": money(cash), "lowest_balance": money(low), "lowest_date": d.isoformat()},
        display={
            "cash_now": uz.format_mln(cash),
            "lowest_balance": uz.format_mln(low),
            "lowest_date": uz.format_date(d),
        },
        speech={
            "cash_now": uz.speech_amount(cash),
            "lowest_balance": uz.speech_amount(low),
            "lowest_date": uz.uz_ordinal_date(d),
        },
        say=say,
        ui_blocks=[
            {
                "id": "cash",
                "type": "kpi",
                "label": "Hozirgi kassa",
                "value": uz.format_mln_number(cash),
                "unit": "mln so'm",
                "note": "Naqd + bank hisobi",
            },
            forecast_block(base, 60, "fc"),
        ],
        answer={
            "verdict": base.verdict or "info",
            "headline": f"{cash_prefix(ctx.business)} {uz.format_mln(cash)} bor.",
            "reason": f"{headline} Eng qiyin kun — **{uz.format_date(d)}**: kassada {uz.format_mln(low)} qoladi"
            + (f" ({words})." if words else "."),
            "steps": [
                s["text"] if not s.get("label") else f"**{s['label']}** — {s['text']}"
                for s in advice.steps(base)
            ],
            "explain": explain_lines(ctx),
            "chips": ["Savdo kamaysa nima bo'ladi?", "Yana 2 ta xodim olsam bo'ladimi?"],
        },
        summary=s60.text,
    )


def forecast_block(base: ForecastResult, days: int, bid: str) -> dict[str, Any]:
    s = advice.horizon_summary(base, days)
    rows = base.daily()[: days + 1]
    return {
        "id": bid,
        "type": "forecast_chart",
        "days": days,
        "series": [
            {
                "i": i,
                "date": r.date.isoformat(),
                "label": uz.format_date_short(r.date),
                "close": money(r.close),
                "p10": money(r.p10),
                "p90": money(r.p90),
                "display": uz.format_mln(r.close),
            }
            for i, r in enumerate(rows)
        ],
        "safe_min": money(base.safe_min),
        "safe_label": f"Xavfsiz chegara · {uz.format_mln(base.safe_min, short=True)}",
        "lowest_index": (s.lowest_date - base.today).days,
        "callout_title": s.callout_title,
        "callout_text": s.callout_text,
        "aria_label": f"Keyingi {days} kun: {s.text.replace('**', '')}",
    }


def get_forecast(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    days = args.get("horizon_days", 60)
    base = ctx.base
    if base.insufficient_data:
        return insufficient()
    s = advice.horizon_summary(base, days)
    weekly = [
        {"date": r.date.isoformat(), "close": money(r.close)} for r in base.daily()[: days + 1 : 7]
    ]
    return envelope(
        verdict=s.verdict,
        facts={
            "horizon_days": days,
            "lowest_balance": money(s.lowest),
            "lowest_date": s.lowest_date.isoformat(),
            "weekly": weekly[:13],
        },
        display={
            "lowest_balance": uz.format_mln(s.lowest),
            "lowest_date": uz.format_date(s.lowest_date),
        },
        speech={
            "lowest_balance": uz.speech_amount(s.lowest),
            "lowest_date": uz.uz_ordinal_date(s.lowest_date),
        },
        say=f"Keyingi {uz.uz_number_words(days)} kunda eng qiyin kun {uz.uz_ordinal_date(s.lowest_date)}, "
        f"o'shanda kassada {uz.speech_amount(s.lowest)} qoladi.",
        ui_blocks=[forecast_block(base, days, "fc")],
        answer={
            "verdict": s.verdict or "info",
            "headline": s.chip + ".",
            "reason": s.text,
            "steps": [x["text"] for x in advice.steps(base)],
            "explain": explain_lines(ctx),
        },
    )


CATEGORY_UZ = {
    "payroll": "Ish haqi",
    "rent": "Ijara",
    "kommunal": "Kommunal",
    "tax": "Soliq",
    "loan": "Kredit",
    "doimiy": "Doimiy xizmatlar (internet, reklama)",
    "supplier": "Ta'minotchilar",
    "xom ashyo": "Mahsulot xaridi",
    "qadoq": "Qadoqlash",
    "yetkazish": "Yetkazish va taksi",
    "xo'jalik": "Xo'jalik mollari",
    "bank komissiyasi": "Bank komissiyasi",
    "kunbay": "Kunbay ishchilar",
    "ta'mirlash": "Ta'mirlash",
    "capex": "Asosiy vositalar (bir martalik)",
    "dividend": "Dividend",
    "avans": "Berilgan avans",
    "financing": "Kapital va kreditlar",
    "savdo": "Savdo",
    "boshqa": "Boshqa",
}
ONE_OFF = ("capex", "dividend", "avans", "financing")


def _month_start(d: date, back: int = 0) -> date:
    y, m = divmod(d.month - 1 - back, 12)
    return date(d.year + y, m + 1, 1)


def get_expenses(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Monthly expenses and income by category from the ledger (last complete months)."""
    from django.db.models import Max
    from django.db.models.functions import TruncMonth

    months = int(args.get("months", 3))
    last = Transaction.objects.filter(is_actual=True).aggregate(m=Max("txn_date"))["m"]
    if last is None:
        return envelope(
            ok=True,
            say="Jadvalda xarajat yozuvlari hali yo'q.",
            answer={
                "verdict": "info",
                "headline": "Jadvalda xarajat yozuvlari hali yo'q.",
                "reason": "",
                "steps": [],
            },
        )
    end = _month_start(last) if last.day >= 25 else _month_start(last, 1)
    starts = [_month_start(end, k) for k in range(months)]
    rows = (
        Transaction.objects.filter(
            is_actual=True, txn_date__gte=starts[-1], txn_date__lt=_month_start(end, -1)
        )
        .annotate(m=TruncMonth("txn_date"))
        .values("m", "direction", "category")
        .annotate(s=Sum("amount"))
    )
    out: dict[date, dict[str, Decimal]] = {m: {} for m in starts}
    inc: dict[date, Decimal] = dict.fromkeys(starts, Decimal(0))
    for r in rows:
        m = r["m"].date() if isinstance(r["m"], datetime) else r["m"]
        cat = r["category"] or "boshqa"
        if r["direction"] == "out":
            out.setdefault(m, {})[cat] = out.get(m, {}).get(cat, Decimal(0)) + r["s"]
        elif cat not in ONE_OFF:
            inc[m] = inc.get(m, Decimal(0)) + r["s"]

    def operating(m: date) -> Decimal:
        return sum((v for c, v in out.get(m, {}).items() if c not in ONE_OFF), Decimal(0))

    last_m = starts[0]
    total = operating(last_m)
    avg = (sum((operating(m) for m in starts), Decimal(0)) / len(starts)).quantize(Decimal(1))
    cats = sorted(
        ((c, v) for c, v in out.get(last_m, {}).items() if c not in ONE_OFF), key=lambda kv: -kv[1]
    )
    one_off = sum((v for c, v in out.get(last_m, {}).items() if c in ONE_OFF), Decimal(0))
    label = f"{uz.MONTHS[last_m.month - 1]} {last_m.year}"
    top = ", ".join(f"{CATEGORY_UZ.get(c, c)} {uz.format_mln(v)}" for c, v in cats[:3])
    net = inc.get(last_m, Decimal(0)) - total
    headline = f"{label.capitalize()}: xarajatlar {uz.format_mln(total)}, tushum {uz.format_mln(inc.get(last_m, Decimal(0)))}"
    reason = (
        f"Eng kattalari: {top}. Oxirgi {months} oyda o'rtacha oyiga {uz.format_mln(avg)} xarajat. "
        f"Sof natija: {uz.format_mln(net, signed=True)}."
    )
    if one_off:
        reason += f" Bundan tashqari bir martalik to'lovlar: {uz.format_mln(one_off)}."
    from .detail_tools import products_for_month

    products = products_for_month(ctx, last_m.isoformat())
    if products:
        reason += (
            " Mahsulot xaridlari: "
            + ", ".join(f"{x['name']} {x['amount']}" for x in products[:6])
            + "."
        )
    return envelope(
        facts={
            "month": last_m.isoformat(),
            "expenses": money(total),
            "income": money(inc.get(last_m, Decimal(0))),
            "net": money(net),
            "avg_expenses": money(avg),
            "one_off": money(one_off),
            "products": products,
            "by_category": [
                {"category": CATEGORY_UZ.get(c, c), "amount": money(v)} for c, v in cats[:10]
            ],
            "months": [
                {
                    "month": m.isoformat(),
                    "expenses": money(operating(m)),
                    "income": money(inc.get(m, Decimal(0))),
                }
                for m in starts
            ],
        },
        display={
            "expenses": uz.format_mln(total),
            "income": uz.format_mln(inc.get(last_m, Decimal(0))),
            "avg": uz.format_mln(avg),
            "by_category": {CATEGORY_UZ.get(c, c): uz.format_mln(v) for c, v in cats[:10]},
        },
        say=f"{label.capitalize()} oyida xarajatlar {uz.speech_amount(total)}, tushum {uz.speech_amount(inc.get(last_m, Decimal(0)))}.",
        ui_blocks=[
            {
                "id": "exp",
                "type": "kpi",
                "label": f"Xarajatlar · {label}",
                "value": uz.format_mln_number(total),
                "unit": "mln so'm",
                "note": f"o'rtacha oyiga {uz.format_mln(avg)}",
            },
            {
                "id": "inc",
                "type": "kpi",
                "label": f"Tushum · {label}",
                "value": uz.format_mln_number(inc.get(last_m, Decimal(0))),
                "unit": "mln so'm",
                "note": f"sof: {uz.format_mln(net, signed=True)}",
            },
            {
                "id": "cats",
                "type": "steps",
                "items": [
                    {
                        "label": CATEGORY_UZ.get(c, c),
                        "text": uz.format_mln(v),
                        "severity": "warning" if i < 3 else "success",
                    }
                    for i, (c, v) in enumerate(cats[:8])
                ],
            },
        ],
        answer={
            "verdict": "info",
            "headline": headline,
            "reason": reason,
            "steps": [],
            "explain": explain_lines(ctx),
        },
    )


def get_upcoming_payments(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    days = args.get("days", 30)
    base = ctx.base
    due = [p for p in base.obligations if base.today < p.date <= base.today + timedelta(days=days)]
    total = sum((p.amount for p in due), Decimal(0))
    items = [
        {
            "label": f"{uz.format_date(p.date)} · {advice.PRIORITY_LABEL[p.priority].lower()}",
            "text": f"{p.title} — {uz.format_mln(p.amount)}",
            "severity": "danger" if p.priority == "critical" else "warning",
        }
        for p in due[:10]
    ]
    return envelope(
        facts={
            "days": days,
            "count": len(due),
            "total": money(total),
            "payments": [
                {
                    "date": p.date.isoformat(),
                    "title": p.title,
                    "amount": money(p.amount),
                    "priority": p.priority,
                }
                for p in due[:10]
            ],
        },
        display={"total": uz.format_mln(total), "count": str(len(due))},
        speech={"total": uz.speech_amount(total), "count": uz.uz_number_words(len(due))},
        say=f"Keyingi {uz.uz_number_words(days)} kunda {uz.uz_number_words(len(due))} ta to'lov bor, jami {uz.speech_amount(total)}."
        + (
            f" Eng yaqini {uz.uz_ordinal_date(due[0].date)}: {due[0].title}, {uz.speech_amount(due[0].amount)}."
            if due
            else ""
        ),
        ui_blocks=[{"id": "pays", "type": "steps", "items": items}],
        answer={
            "verdict": "info",
            "headline": f"{days} kunda {len(due)} ta to'lov, jami {uz.format_mln(total)}.",
            "reason": "Majburiy to'lovlar sanasida pul tayyor turishi kerak.",
            "steps": [],
            "explain": explain_lines(ctx),
        },
    )


def _purchase_reason(
    base: ForecastResult, key: date, value: Decimal, amount: Decimal
) -> tuple[str, str]:
    p = main_payment(base, key)
    phrase = (
        PAY_PHRASE.get(p.category, f"{uz.add_case(p.counterparty or p.title, 'ga')} to'lashga")
        if p
        else "to'lovlarga"
    )
    amount_text = uz.format_mln(amount, short=True).replace(" mln", " million")
    reason = (
        f"Agar hozir {amount_text} sarflasangiz, **{uz.format_date(key, 'da')}** {phrase} "
        f"{uz.format_mln(-value).replace(' mln', ' million')} so'm yetmay qoladi."
    )
    day_kind = PAY_DAY.get(p.category, "to'lov kuni") if p else "eng qiyin kun"
    return reason, day_kind


def evaluate_purchase_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    amount = Decimal(args["amount"])
    if amount <= 0 or amount > Decimal(10_000_000_000):
        raise ToolArgError("amount must be 1..10 000 000 000 so'm")
    base, inp = ctx.base, ctx.cached.inp
    if base.insufficient_data:
        return insufficient()
    on = args.get("date") or base.today
    if on < base.today:
        raise ToolArgError("date must not be in the past")
    inst = args.get("installments")
    d = evaluate_purchase(inp, amount, on_date=on, installments=inst, base=base)
    req, rec = d.requested, d.recommended
    key = d.key_date
    facts: dict[str, Any] = {
        "amount": money(amount),
        "purchase_date": on.isoformat(),
        "verdict": d.verdict,
        "key_date": key.isoformat(),
        "balance_on_key_date_if_now": money(req.balance_on_key_date),
        "lowest_balance": money(req.min_balance),
    }
    display = {
        "amount": uz.format_mln(amount),
        "key_date": uz.format_date(key),
        "lowest_balance": uz.format_mln(req.min_balance),
    }
    speech = {
        "amount": uz.speech_amount(amount),
        "key_date": uz.uz_ordinal_date(key),
        "lowest_balance": uz.speech_amount(req.min_balance),
    }
    rec_date = rec.schedule[0][0] if rec and rec.kind == "earliest_safe_date" else None
    if rec_date:
        facts["recommended_date"] = rec_date.isoformat()
        display["recommended_date"] = uz.format_date(rec_date)
        speech["recommended_date"] = uz.uz_ordinal_date(rec_date)
    split = next((a for a in d.alternatives if a.kind == "installments"), None)
    if split:
        facts["installments"] = [
            {"date": dt.isoformat(), "amount": money(a)} for dt, a in split.schedule
        ]
        facts["installments_lowest_balance"] = money(split.min_balance)
        facts["installments_verdict"] = split.verdict
        display["installments_lowest_balance"] = uz.format_mln(split.min_balance)
        speech["installments_lowest_balance"] = uz.speech_amount(split.min_balance)
    limit = spend_limit_until(base, key) if key > base.today else Decimal(0)
    facts["spend_limit"] = money(limit)
    display["spend_limit"] = uz.format_mln(limit, short=True)
    speech["spend_limit"] = uz.speech_amount(limit)

    blocks: list[dict[str, Any]] = []
    steps: list[str] = []
    plan = None
    if d.verdict == "yes":
        headline = "Ha, olsangiz bo'ladi."
        reason = (
            f"Xariddan keyin ham eng qiyin kuni kassada {uz.format_mln(req.min_balance)} qoladi."
        )
        say = f"Ha, olsangiz bo'ladi. Xariddan keyin ham eng qiyin kuni {uz.speech_amount(req.min_balance)} qoladi."
        steps = [
            f"Xaridni **{uz.format_date(on, 'da')}** qilishingiz mumkin.",
            f"Shundan keyin {uz.format_date(req.min_date, 'gacha')} boshqa katta xarajat qilmang.",
        ]
    else:
        if req.balance_on_key_date < 0:
            reason, day_kind = _purchase_reason(base, key, req.balance_on_key_date, amount)
            headline = "Yo'q, hozir olmang." if d.verdict == "no" else "Olsa bo'ladi, lekin xavfli."
        else:
            day_kind = "eng qiyin kun"
            headline = "Hozir olmang, xavfli."
            reason = f"Xariddan keyin **{uz.format_date(req.min_date, 'da')}** kassa xavfsiz chegaradan pastga, {uz.format_mln(req.min_balance)} gacha tushadi."
        rows = [
            {
                "label": "Hozir olsangiz",
                "value": money(req.balance_on_key_date),
                "display": uz.format_mln(req.balance_on_key_date, signed=True),
                "status": "bad" if req.balance_on_key_date < 0 else "warn",
                "status_text": "Yetmaydi" if req.balance_on_key_date < 0 else "Tor",
            }
        ]
        say_parts = [headline.replace("Olsa bo'ladi, lekin xavfli.", "Ehtiyot bo'ling.")]
        if req.balance_on_key_date < 0:
            p = main_payment(base, key)
            what = advice.payment_word(p) if p else "to'lovlar"
            say_parts.append(
                f"Agar hozir olsangiz, {uz.uz_ordinal_date(key, 'da')} {uz.add_case(what, 'ga')} "
                f"{uz.speech_amount(-req.balance_on_key_date)} yetmay qoladi."
            )
        if rec_date and rec:
            rows.append(
                {
                    "label": f"{uz.format_date(rec_date, 'da')} olsangiz",
                    "value": money(rec.balance_on_key_date),
                    "display": uz.format_mln(rec.balance_on_key_date, signed=True),
                    "status": "ok",
                    "status_text": "Yetadi",
                }
            )
            steps.append(
                f"Xaridni **{uz.format_date(rec_date, 'da')}** qiling — o'shanda hamma to'lovlarga pul yetadi."
            )
            say_parts.append(f"Xaridni {uz.uz_ordinal_date(rec_date, 'da')} qiling.")
            summary = (
                f"{uz.format_date(rec_date)} 09:00 — xarid eslatmasi ({uz.format_mln(amount)})"
            )
            plan = propose(
                ctx,
                ActionPlan.Kind.PURCHASE_PLAN,
                {"amount": money(amount), "date": rec_date.isoformat(), "summary": summary},
                rec_date,
            )
        if limit > 0 and key > base.today:
            steps.append(
                f"{uz.format_date(key, 'gacha')} **{uz.format_mln(limit, short=True).replace(' mln', ' million')} so'mdan katta** xarid qilmang."
            )
        if plan:
            steps.append(
                f"{uz.format_date(rec_date) if rec_date else ''} ertalab sizga o'zim eslataman.".strip()
            )
            say_parts.append("Shunday reja tuzaymi?")
        blocks.append(
            {
                "id": "cmp",
                "type": "compare_bars",
                "title": (
                    "Bugun, xariddan keyin — kassada qancha pul qoladi?"
                    if key == base.today
                    else f"{uz.format_date(key)}, {day_kind} — kassada qancha pul qoladi?"
                ),
                "rows": rows,
            }
        )
        say = " ".join(say_parts)
    split_line = ""
    if split:
        split_line = "Bo'lib to'lash ham ko'rib chiqildi: " + (
            "pul yetadi, lekin xavfsiz chegaradan pastga tushadi"
            if split.verdict == "risky"
            else "pul yetadi"
            if split.verdict == "yes"
            else "u ham yetmaydi"
        )
    answer = {
        "verdict": d.verdict,
        "headline": headline,
        "reason": reason,
        "steps": steps[:3],
        "explain": explain_lines(ctx, split_line),
        "chips": ["Boshqa yo'l bormi?"] if d.verdict != "yes" else [],
    }
    return envelope(
        verdict=d.verdict,
        facts=facts,
        display=display,
        speech=speech,
        say=say,
        ui_blocks=blocks,
        answer=answer,
        proposed_plan=plan,
    )


def simulate_change_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base, inp = ctx.base, ctx.cached.inp
    if base.insufficient_data:
        return insufficient()
    kind = args["kind"]
    value = Decimal(args["value"])
    change = Change(
        kind=kind,
        value=value,
        start_date=args.get("start_date"),
        counterparty=args.get("counterparty"),
    )
    try:
        s = simulate(base, inp, change)
    except StaffCountUnknown:
        q = "Hozir nechta xodimingiz bor?"
        return envelope(
            ok=False,
            facts={"needs": "staff_count"},
            say=q,
            answer={
                "verdict": "info",
                "headline": q,
                "reason": "Yangi xodim narxini hisoblash uchun hozirgi xodimlar soni kerak. Bir marta ayting, eslab qolaman.",
                "steps": [],
            },
        )
    except EngineError as exc:
        raise ToolArgError(str(exc)) from exc
    card = advice.scenario_card(base, s, kind="other")
    i = card["marker_index"]
    d = base.date_at(i)
    value_on = s.close_on(d)
    say = f"{card['title']}. {uz.uz_ordinal_date(d, 'da')} kassada " + (
        f"{uz.speech_amount(value_on)} qoladi."
        if value_on >= 0
        else f"{uz.speech_amount(-value_on)} yetmay qoladi."
    )
    return envelope(
        verdict=card["verdict"],
        facts={
            "kind": kind,
            "value": str(value),
            "date": d.isoformat(),
            "balance": money(value_on),
            "lowest_balance": money(s.min_balance),
        },
        display={"date": uz.format_date(d), "balance": uz.format_mln(value_on)},
        speech={"date": uz.uz_ordinal_date(d), "balance": uz.speech_amount(value_on)},
        say=say,
        ui_blocks=[
            {
                "id": "cmp",
                "type": "compare_bars",
                "title": f"{uz.format_date(d)} — kassada qancha pul qoladi?",
                "rows": [
                    {
                        "label": "Hozirgi holat",
                        "value": money(base.close_on(d)),
                        "display": uz.format_mln(base.close_on(d), signed=True),
                        "status": "ok" if base.close_on(d) >= base.safe_min else "warn",
                        "status_text": "Yetadi" if base.close_on(d) >= 0 else "Yetmaydi",
                    },
                    {
                        "label": "O'zgarishdan keyin",
                        "value": money(value_on),
                        "display": uz.format_mln(value_on, signed=True),
                        "status": "ok"
                        if value_on >= base.safe_min
                        else "warn"
                        if value_on >= 0
                        else "bad",
                        "status_text": "Yetadi" if value_on >= 0 else "Yetmaydi",
                    },
                ],
            }
        ],
        answer={
            "verdict": card["verdict"],
            "headline": card["title"] + ".",
            "reason": f"{card['body']['before']}**{card['body']['strong']}**{card['body']['after']}",
            "steps": [card["tip"].removeprefix("Maslahat: ")],
            "explain": explain_lines(ctx),
        },
    )


def explain_day_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = ctx.base
    d = args["date"]
    if not base.today <= d <= base.end:
        raise ToolArgError("date is outside the forecast window")
    bd = explain_day(base, d)
    rows = [
        {"label": "Kun boshida kassada", "value": uz.format_mln(bd.opening), "tone": "plain"},
        {
            "label": "Savdodan kiradi",
            "value": uz.format_mln(bd.net_trading, signed=True),
            "tone": "success",
        },
        *[
            {
                "label": advice.payment_label(p),
                "badge": "majburiy" if p.priority == "critical" else "",
                "value": uz.format_mln(-p.amount),
                "tone": "danger",
            }
            for p in bd.payments
        ],
    ]
    return envelope(
        facts={
            "date": d.isoformat(),
            "opening": money(bd.opening),
            "net_trading": money(bd.net_trading),
            "payments": [{"title": p.title, "amount": money(p.amount)} for p in bd.payments],
            "closing": money(bd.closing),
        },
        display={
            "date": uz.format_date(d),
            "opening": uz.format_mln(bd.opening),
            "closing": uz.format_mln(bd.closing),
        },
        speech={
            "date": uz.uz_ordinal_date(d),
            "opening": uz.speech_amount(bd.opening),
            "closing": uz.speech_amount(bd.closing),
        },
        say=f"{uz.uz_ordinal_date(d).capitalize()} kuni boshida {uz.speech_amount(bd.opening)} bo'ladi, oxirida {uz.speech_amount(bd.closing)} qoladi.",
        ui_blocks=[
            {
                "id": "day",
                "type": "day_breakdown",
                "title": uz.format_date(d),
                "rows": rows,
                "closing": uz.format_mln(bd.closing),
            }
        ],
        answer={
            "verdict": "info",
            "headline": f"{uz.format_date(d)}: kun oxirida {uz.format_mln(bd.closing)} qoladi.",
            "reason": advice.day_advice(base, d),
            "steps": [],
        },
    )


def propose_plan_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    kind = args["kind"]
    d: date | None = args.get("date")
    amount = Decimal(args["amount"]) if args.get("amount") is not None else None
    note = args.get("note", "")
    if d and d < ctx.base.today:
        raise ToolArgError("date must not be in the past")
    label = {
        "reminder": "eslatma",
        "spending_limit": "xarajat chegarasi",
        "purchase_plan": "xarid rejasi",
    }[kind]
    summary = " — ".join(
        x
        for x in (
            f"{uz.format_date(d)} 09:00" if d else "",
            label + (f" ({uz.format_mln(amount)})" if amount else ""),
            note,
        )
        if x
    )
    plan = propose(
        ctx,
        kind,
        {
            "date": d.isoformat() if d else None,
            "amount": money(amount) if amount else None,
            "note": note,
            "summary": summary,
        },
        d,
    )
    return envelope(
        facts={"plan_id": plan["id"]},
        display={"summary": summary},
        say="Shunday reja tuzaymi?",
        proposed_plan=plan,
    )


def confirm_plan_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """Only after an explicit "ha" from the user (checked here, not trusted to the LLM)."""
    from .plans import approve_plan

    if not AFFIRMATIVE.match(ctx.last_user_text or ""):
        return envelope(
            ok=False, facts={"error": "no_explicit_consent"}, say="Avval aniq «ha» deb tasdiqlang."
        )
    plan = approve_plan(
        ctx.business, int(args["plan_id"]), ctx.user_id, actor=f"{ctx.channel}:user:{ctx.user_id}"
    )
    return envelope(
        facts={"plan_id": plan.pk, "status": plan.status},
        display={"summary": plan.payload.get("summary", "")},
        say="Reja tasdiqlandi. Vaqti kelganda eslataman.",
    )


def remember_fact_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from apps.knowledge.learning import candidate_from_text

    cand = candidate_from_text(ctx, args["text"])
    if cand is None:
        return envelope(
            ok=False,
            say="Buni qoida sifatida tushunmadim. Boshqacha aytib bering.",
            answer={
                "verdict": "info",
                "headline": "Tushunmadim.",
                "reason": "Buni qoida sifatida tushunmadim. Masalan: «Agro Go'shtga doim 15 kun kechiktirib to'laymiz».",
                "steps": [],
            },
        )
    return envelope(
        facts={"candidate_id": cand["id"]},
        say=cand["say"],
        candidate=cand,
        answer={
            "verdict": "info",
            "headline": "Tushundim, eslab qoldim.",
            "reason": cand["text"],
            "steps": [],
        },
    )


def set_staff_count_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    n = int(args["count"])
    Business.objects.filter(pk=ctx.business.pk).update(staff_count=n)
    ctx.business.staff_count = n
    refresh_forecast(ctx.business)
    ctx._cached = None
    return envelope(
        facts={"staff_count": n},
        display={"staff_count": str(n)},
        speech={"staff_count": uz.uz_number_words(n)},
        say=f"Eslab qoldim: {uz.uz_number_words(n)} ta xodim.",
    )


DATE = {"type": "string", "format": "date", "description": "Sana YYYY-MM-DD"}
TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "get_cash_status",
            "Hozirgi kassa, bugungi holat va eng qiyin kun.",
            {"type": "object", "properties": {}},
            get_cash_status,
        ),
        Tool(
            "get_forecast",
            "Kassa prognozi: kunlik qoldiq, eng past nuqta, qaror.",
            {
                "type": "object",
                "properties": {
                    "horizon_days": {
                        "type": "integer",
                        "enum": [7, 30, 60, 90],
                        "description": "Necha kunlik prognoz",
                    }
                },
            },
            get_forecast,
        ),
        Tool(
            "get_expenses",
            "O'tgan oylar xarajatlari va tushumi: oylik jami, kategoriyalar bo'yicha (ish haqi, ijara, mahsulot xaridi...), o'rtacha.",
            {
                "type": "object",
                "properties": {"months": {"type": "integer", "minimum": 1, "maximum": 12}},
            },
            get_expenses,
        ),
        Tool(
            "get_upcoming_payments",
            "Yaqin kunlardagi majburiy va boshqa to'lovlar ro'yxati.",
            {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
            },
            get_upcoming_payments,
        ),
        Tool(
            "evaluate_purchase",
            "Xarid yoki katta xarajat qarori: pul yetadimi, qaysi sanada olish xavfsiz, bo'lib to'lash varianti.",
            {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Summa so'mda (25 million = 25000000)",
                    },
                    "date": {**DATE, "description": "Xarid sanasi (ixtiyoriy, bo'lmasa bugun)"},
                    "installments": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 12,
                        "description": "Bo'lib to'lash oylari soni",
                    },
                },
                "required": ["amount"],
            },
            evaluate_purchase_tool,
        ),
        Tool(
            "simulate_change",
            "«Agar…» savollari: savdo foizga o'zgarsa, yangi xodim olinsa, qo'shimcha xarajat yoki to'lov kechiktirilsa.",
            {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["revenue_pct", "new_staff", "extra_expense", "payment_delay"],
                    },
                    "value": {
                        "type": "number",
                        "description": "revenue_pct: foiz (-20); new_staff: odam soni; extra_expense: so'm; payment_delay: kun",
                    },
                    "start_date": DATE,
                    "counterparty": {"type": "string", "maxLength": 120},
                },
                "required": ["kind", "value"],
            },
            simulate_change_tool,
        ),
        Tool(
            "explain_day",
            "Bitta kun tafsiloti: boshida qancha, savdodan kirim, har bir to'lov, oxirida qancha.",
            {"type": "object", "properties": {"date": DATE}, "required": ["date"]},
            explain_day_tool,
        ),
        Tool(
            "propose_plan",
            "Reja yoki eslatma TAKLIF qilish (bajarmaydi, foydalanuvchi tasdiqlashi kerak).",
            {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["reminder", "spending_limit", "purchase_plan"],
                    },
                    "date": DATE,
                    "amount": {"type": "integer", "minimum": 1},
                    "note": {"type": "string", "maxLength": 200},
                },
                "required": ["kind"],
            },
            propose_plan_tool,
        ),
        Tool(
            "confirm_plan",
            "Foydalanuvchi aniq «ha» deganidan keyin taklif qilingan rejani tasdiqlash.",
            {
                "type": "object",
                "properties": {"plan_id": {"type": "integer", "minimum": 1}},
                "required": ["plan_id"],
            },
            confirm_plan_tool,
        ),
        Tool(
            "remember_fact",
            "Foydalanuvchi aytgan biznes qoidasini eslab qolish uchun taklif yaratish (masalan: «X ga doim 15 kun kechiktirib to'laymiz»).",
            {
                "type": "object",
                "properties": {"text": {"type": "string", "maxLength": 300}},
                "required": ["text"],
            },
            remember_fact_tool,
        ),
        Tool(
            "set_staff_count",
            "Foydalanuvchi aytgan xodimlar sonini profilga yozish.",
            {
                "type": "object",
                "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 10000}},
                "required": ["count"],
            },
            set_staff_count_tool,
        ),
    ]
}


# forecasts and decisions: replaced by "not enough data yet" under MIN_HISTORY_DAYS
SHORT_HISTORY_BLOCKED = frozenset(
    {"get_forecast", "evaluate_purchase", "simulate_change", "explain_day", "propose_plan"}
)


def run_tool(ctx: ToolContext, name: str, raw_args: Any) -> dict[str, Any]:
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolArgError(f"unknown tool {name}")
    args = validate(tool.parameters, raw_args or {})
    if name in SHORT_HISTORY_BLOCKED and ctx.short_history:
        return insufficient()
    return tool.handler(ctx, args)


# advisor tools (apps/ai/advisor_tools.py) join the same registry, args validation and API
from .advisor_tools import ADVISOR_TOOLS  # noqa: E402

TOOLS.update({t.name: t for t in ADVISOR_TOOLS})

# CFO and item-level tools register themselves into TOOLS (safe in any import order).
from . import cfo_tools, detail_tools  # noqa: E402, F401

"""Catalogue intents (Tier 2). Shared facts come from ONE module (`facts`) so every answer shows the
same cash / tightest day / loan / load numbers as Q1–Q4. Each intent: deterministic compute → card."""

from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.engine.cfo import break_even, last_month, pl_value

from . import uz_format as uz
from .catalog import IMPLEMENTED, CatalogItem
from .tools import ToolContext, envelope, propose

D0 = Decimal(0)
DAYS_UZ = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]


def _d(x: Any) -> Decimal:
    try:
        return Decimal(str(x))
    except Exception:
        return D0


def M(x: Any) -> str:
    v = _d(x)
    return uz.format_som(v.quantize(Decimal(1))) if abs(v) < 1_000_000 else uz.format_mln(v)


def N(x: Any) -> str:
    return uz.group_digits(int(_d(x).quantize(Decimal(1), ROUND_HALF_UP)))


def Dt(d: date) -> str:
    return f"{d.day}-{uz.MONTHS[d.month - 1]} {d.year}"


def say_mln(x: Any) -> str:
    v = (abs(_d(x)) / 1_000_000).quantize(Decimal(1), ROUND_HALF_UP)
    return f"{uz.uz_number_words(int(v))} million"


# --- shared facts (single source of truth) -------------------------------------------------------
def summary() -> dict[str, Any]:
    from apps.integrations.models import DataSource

    src = DataSource.objects.exclude(summary={}).order_by("-last_synced_at").first()
    return (src.summary or {}) if src else {}


def facts(ctx: ToolContext) -> dict[str, Any]:
    """Cash, daily forecast, obligations, safe buffer, tightest day, loan — shared by all answers."""
    base = ctx.base
    s = summary()
    today = base.today
    n = min(base.horizon_days, 120)
    days = [base.date_at(i) for i in range(n)]
    close = {d: _d(base.close_on(d)) for d in days}
    obl = [o for o in base.obligations if today < o.date <= today + timedelta(days=n)]
    next30 = sum((_d(o.amount) for o in obl if o.date <= today + timedelta(days=30)), D0)
    buffer = (next30 * 7 / 30).quantize(Decimal(1))
    loan = None
    for b in (s.get("details") or {}).get("counterparties") or []:
        if "kredit" in str(b.get("type", "")).lower() or "bank" in b["name"].lower():
            months = sorted((k, _d(v)) for k, v in (b.get("months") or {}).items())
            bal = next((v for k, v in reversed(months) if k <= today.isoformat()), _d(b["balance"]))
            if bal > 0:
                prin = next(
                    (
                        months[i - 1][1] - months[i][1]
                        for i in range(len(months) - 1, 0, -1)
                        if months[i - 1][1] > months[i][1]
                    ),
                    D0,
                )
                loan = {"name": b["name"], "balance": bal, "principal": prin}
    if loan is None and s.get("loan"):
        loan = {
            "name": s["loan"].get("lender", "Kredit"),
            "balance": _d(s["loan"].get("balance")),
            "principal": _d(s["loan"].get("principal_monthly")),
        }
    return {
        "s": s,
        "base": base,
        "today": today,
        "days": days,
        "close": close,
        "cash": close[today],
        "obligations": obl,
        "buffer": buffer,
        "min_date": base.min_date,
        "min_balance": _d(base.min_balance),
        "loan": loan,
        "accuracy": ((getattr(ctx.business, "data_quality", None) or {}).get("accuracy") or {}),
    }


def card(
    item: CatalogItem,
    verdict: str,
    kpis: list[tuple[str, str, str, str]],
    *,
    chart: dict[str, Any] | None = None,
    table: tuple[list[str], list[list[str]]] | None = None,
    actions: list[str] | None = None,
    assumptions: str = "",
    source: str = "",
    live: str = "",
    ctx: ToolContext | None = None,
    plan: str | None = None,
    facts_out: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    if chart:
        sections.append(
            {
                "id": "chart",
                "title": chart.pop("title", item.chart.split(":")[-1].strip() or "Grafik"),
                "chart": chart,
            }
        )
    if table:
        sections.append(
            {
                "id": "table",
                "title": item.table.split(":")[0] if item.table else "Jadval",
                "table": {"columns": table[0], "rows": table[1]},
            }
        )
    sections.append(
        {"id": "actions", "title": "Nima qilish kerak", "actions": actions or item.actions}
    )
    report = {
        "type": "report",
        "variant": "catalog",
        "id": f"cat_{item.intent}",
        "intent": item.intent,
        "verdict": verdict,
        "verdict_highlight": "",
        "kpis": [{"label": a, "value": b, "sub": c, "tone": t} for a, b, c, t in kpis],
        "sections": sections,
        "assumptions": assumptions,
        "source": source or item.sources,
    }
    chips = [c for c in item.side][:3]
    md_lines = [f"**{verdict}**"]
    if table:
        md_lines += [
            "",
            "| " + " | ".join(table[0]) + " |",
            "|" + "---|" * len(table[0]),
            *["| " + " | ".join(r) + " |" for r in table[1][:12]],
        ]
    md_lines += ["", "CHIPS: " + " | ".join(chips)] if chips else []
    plan_obj = None
    if plan and ctx is not None:
        due = ctx.base.today if not ctx.base.insufficient_data else None
        plan_obj = propose(
            ctx,
            "reminder",
            {"summary": plan, "note": f"catalog:{item.id}"},
            due + timedelta(days=1) if due else None,
        )
    speech = [{"cue": "verdict+kpi", "text": live or verdict}]
    if plan_obj:
        speech.append({"cue": "approve_button", "text": "Tasdiqlaysizmi?"})
    return envelope(
        ok=True,
        facts=facts_out or {},
        md="\n".join(md_lines),
        say=live or verdict,
        speech_segments=speech,
        speech_short=live or verdict,
        ui_blocks=[report],
        proposed_plan=plan_obj,
        answer={"headline": verdict, "reason": ""},
        catalog=item.id,
    )


def cash_chart(
    f: dict[str, Any], n: int, extra: dict[date, Decimal] | None = None
) -> dict[str, Any]:
    days = f["days"][:n]
    series = [
        {
            "name": "Kassa (prognoz)",
            "color": "#14B8A6",
            "data": [float((f["close"][d] / 1_000_000).quantize(Decimal("0.1"))) for d in days],
        }
    ]
    if extra:
        series.append(
            {
                "name": "Sarflansa",
                "color": "#F87171",
                "data": [
                    float(((f["close"][d] - extra.get(d, D0)) / 1_000_000).quantize(Decimal("0.1")))
                    for d in days
                ],
            }
        )
    return {
        "type": "line_multi",
        "unit": "mln so'm",
        "x_labels": [d.strftime("%d.%m.%Y") for d in days],
        "series": series,
        "ref_lines": [
            {
                "y": float((f["buffer"] / 1_000_000).quantize(Decimal("0.1"))),
                "label": "Xavfsiz chegara",
                "color": "#F59E0B",
            }
        ],
    }


def pay_rows(obl: list[Any], limit: int = 10) -> list[list[str]]:
    return [[Dt(o.date), o.title, N(o.amount)] for o in obl[:limit]]


def register(
    intent: str,
) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    def deco(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        IMPLEMENTED[intent] = fn
        return fn

    return deco


# --- S18 cash_risk_3m -------------------------------------------------------------------------
@register("cash_risk_3m")
def cash_risk_3m(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    n = min(int(p.get("horizon_days") or 90), len(f["days"]))
    d_min = min(f["days"][:n], key=lambda d: f["close"][d])
    v_min = f["close"][d_min]
    risk = v_min < f["buffer"]
    pays = [o for o in f["obligations"] if o.date == d_min]
    why = (
        (" — " + ", ".join(o.title.split(" · ")[0].lower() for o in pays) + " kuni") if pays else ""
    )
    verdict = f"Katta xavf {'bor' if risk else 'yo‘q'}. Eng tang kun — {Dt(d_min)}{why}: qoldiq ~{M(v_min)} (chegara {M(f['buffer'])})."
    live = f"Uch oyda pul {'uzilishi mumkin' if risk else 'uzilmaydi'}. Eng tang kun — {d_min.day}-{uz.MONTHS[d_min.month - 1]}."
    return card(
        item,
        verdict,
        [
            ("Eng tang nuqta", Dt(d_min), why.strip(" —"), "bad" if risk else ""),
            ("Eng past qoldiq", M(v_min), f"{n} kun ichida", "bad" if risk else "good"),
            ("Xavfsiz chegara", M(f["buffer"]), "7 kunlik majburiy chiqim", ""),
        ],
        chart={"title": f"{n} kunlik kunlik kassa", **cash_chart(f, n)},
        table=(
            ["Sana", "To'lov", "Summa"],
            pay_rows([o for o in f["obligations"] if o.date <= f["today"] + timedelta(days=n)], 15),
        ),
        assumptions="Xavfsiz chegara = keyingi 30 kun majburiy to'lovlarining 7 kunlik ulushi. Prognoz — kunlik model (Smena + Kassa + to'lov kalendari).",
        source="Kunlik prognoz (Smena, Kassa, Ish haqi, Hisoblash, Kontragentlar)",
        live=live,
        ctx=ctx,
        facts_out={
            "min_date": d_min.isoformat(),
            "min_balance": M(v_min),
            "buffer": M(f["buffer"]),
        },
    )


# --- N01 safe_to_spend -------------------------------------------------------------------------
@register("safe_to_spend")
def safe_to_spend(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    pay = next((o for o in f["obligations"] if o.category == "payroll"), None)
    until = pay.date if pay else f["today"] + timedelta(days=30)
    window = [d for d in f["days"] if d <= until]
    d_min = min(window, key=lambda d: f["close"][d])
    safe = max(D0, f["close"][d_min] - f["buffer"])
    amount = _d(p.get("amount")) if p.get("amount") else None
    extra = {d: amount for d in f["days"]} if amount else None
    if amount:
        ok = amount <= safe
        verdict = (
            f"{M(amount)} sarflasangiz {'ham kassa xavfsiz qoladi' if ok else 'kassa chegaradan pastga tushadi'}: {Dt(d_min)}da {M(f['close'][d_min] - amount)} qoladi (chegara {M(f['buffer'])}). "
            f"Bemalol summa — {M(safe)}."
        )
    else:
        verdict = f"Bugun {M(safe)} gacha bemalol sarflay olasiz. Undan ortig'i {Dt(d_min)}da kassani chegaradan pastga tushiradi."
    live = f"Bugun {say_mln(safe)} gacha bemalol sarflay olasiz; undan ko'pi {d_min.day}-{uz.MONTHS[d_min.month - 1]}dagi {'oylikka' if pay else 'to‘lovlarga'} xavf soladi."
    return card(
        item,
        verdict,
        [
            ("Bemalol summa", M(safe), f"{Dt(until)} gacha", "good"),
            ("Eng tang kun", Dt(d_min), M(f["close"][d_min]), ""),
            ("Xavfsiz chegara", M(f["buffer"]), "7 kunlik majburiy chiqim", ""),
        ],
        chart={
            "title": "Kunlik kassa (bugun → keyingi oylik)",
            **cash_chart(f, len(window), extra),
        },
        table=(
            ["Sana", "Majburiy to'lov", "Summa"],
            pay_rows([o for o in f["obligations"] if o.date <= until]),
        ),
        actions=[
            f"{M(safe)} gacha — bemalol",
            f"Kattaroq xarid → {Dt(until + timedelta(days=1))} dan keyin",
            "Yoki bo'lib to'lash (N12)",
        ],
        assumptions="Bemalol = keyingi oylik kunigacha kassaning eng past nuqtasi − xavfsiz chegara.",
        source="Kunlik prognoz, Ish haqi, Hisoblash, Kontragentlar",
        live=live,
        ctx=ctx,
        facts_out={"safe": M(safe), "min_date": d_min.isoformat(), "buffer": M(f["buffer"])},
    )


# --- N02 payroll_coverage ----------------------------------------------------------------------
@register("payroll_coverage")
def payroll_coverage(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    pay = next((o for o in f["obligations"] if o.category == "payroll"), None)
    s = f["s"]
    if pay is None:
        verdict = "Keyingi oylik to'lovi kalendarda topilmadi — Ish haqi varag'idan oxirgi oy summasi bilan hisoblang."
        return card(
            item,
            verdict,
            [
                ("Oylik summasi", "—", "", ""),
                ("Kassa", M(f["cash"]), "bugun", ""),
                ("Zaxira", M(f["buffer"]), "", ""),
            ],
            ctx=ctx,
        )
    d = pay.date
    before = f["close"].get(d - timedelta(days=1), f["cash"])
    after = f["close"].get(d, f["cash"])
    ok = after >= f["buffer"]
    verdict = f"{'Ha, yetadi' if ok else 'Yo‘q, yetmasligi mumkin'}: {Dt(d)}da kassa {M(before)}, oylik {M(pay.amount)}, keyin {M(after)} qoladi (chegara {M(f['buffer'])})."
    pay_m = (s.get("details") or {}).get("payroll") or {}
    lm = sorted(pay_m)[-1] if pay_m else None
    rows = (
        [
            [k, N(v[4]), "to'lanadi"]
            for k, v in sorted((pay_m.get(lm) or {}).items(), key=lambda kv: -_d(kv[1][4]))
        ]
        if lm
        else []
    )
    win = [x for x in f["days"] if abs((x - d).days) <= 7]
    live = f"Oylikka pul {'yetadi' if ok else 'yetmasligi mumkin'} — {d.day}-{uz.MONTHS[d.month - 1]}da to'lagandan keyin {say_mln(after)} qoladi."
    chart = cash_chart(f, len(f["days"]))
    idx = [f["days"].index(x) for x in win]
    chart["x_labels"] = [chart["x_labels"][i] for i in idx]
    chart["series"][0]["data"] = [chart["series"][0]["data"][i] for i in idx]
    return card(
        item,
        verdict,
        [
            ("Oylik summasi", M(pay.amount), Dt(d), ""),
            ("Kassa (oylikdan keyin)", M(after), "", "good" if ok else "bad"),
            ("Zaxira", M(after - f["buffer"]), "chegaradan yuqori", "good" if ok else "bad"),
        ],
        chart={"title": "Kassa oylik kuni atrofida (±7 kun)", **chart},
        table=(["Xodim", "Netto (oxirgi oy)", "Holat"], rows),
        source=f"Ish haqi ({lm}), kunlik prognoz",
        live=live,
        ctx=ctx,
        facts_out={"payroll": M(pay.amount), "after": M(after), "date": d.isoformat()},
    )


# --- N03 loan_payment_coverage -----------------------------------------------------------------
@register("loan_payment_coverage")
def loan_payment_coverage(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    loans = [o for o in f["obligations"] if o.category == "loan"]
    loan = f["loan"]
    if not loans or not loan:
        verdict = "Kredit to'lovi kalendarda topilmadi — Kontragentlar varag'ida 'Bank krediti' saldosi va Kassa'da kredit to'lovlari bormi, tekshiring."
        return card(
            item,
            verdict,
            [
                ("Keyingi to'lov", "—", "", ""),
                ("Kassa", M(f["cash"]), "bugun", ""),
                ("Qolgan qarz", "—", "", ""),
            ],
            ctx=ctx,
        )
    nx = loans[0]
    k = f["close"].get(nx.date, f["cash"])
    bal = loan["balance"]
    rate = Decimal("0.24")
    interest = (bal * rate / 12).quantize(Decimal(1))
    principal = loan["principal"] or (_d(nx.amount) - interest)
    rows, b = [], bal
    d0 = nx.date
    for i in range(6):
        if b <= 0:
            break
        it = (b * rate / 12).quantize(Decimal(1))
        pr = min(principal, b)
        b -= pr
        mm = d0.month - 1 + i
        di = date(
            d0.year + mm // 12,
            mm % 12 + 1,
            min(d0.day, calendar.monthrange(d0.year + mm // 12, mm % 12 + 1)[1]),
        )
        rows.append([Dt(di), N(pr), N(it), N(b)])
    ok = k >= nx.amount
    verdict = f"{'Ha' if ok else 'Yo‘q'}: {Dt(nx.date)}da to'lov {M(nx.amount)} (asosiy {M(principal)} + foiz ~{M(interest)}), kassa {M(k)}."
    live = f"Kredit to'loviga pul {'yetadi' if ok else 'yetmasligi mumkin'} — {nx.date.day}-sanada {say_mln(nx.amount)} atrofida to'laysiz."
    chart = {
        "title": "Keyingi 6 oylik to'lovlar (mln so'm)",
        "type": "bar_grouped",
        "x": "label",
        "group_colors": {"asosiy": "#94A3B8", "foiz": "#F87171"},
        "unit": "mln so'm",
        "data": [
            {
                "label": r[0].split()[0] + " " + r[0].split()[1][:3],
                "asosiy": float(_d(r[1].replace(" ", "").replace("\xa0", "")) / 1_000_000),
                "foiz": float(_d(r[2].replace(" ", "").replace("\xa0", "")) / 1_000_000),
            }
            for r in rows
        ],
    }
    return card(
        item,
        verdict,
        [
            ("Keyingi to'lov", M(nx.amount), Dt(nx.date), ""),
            ("Kassa o'sha kuni", M(k), "", "good" if ok else "bad"),
            ("Qolgan qarz", M(bal), f"{loan['name']}", ""),
        ],
        chart=chart,
        table=(["Sana", "Asosiy", "Foiz", "Qoldiq"], rows),
        assumptions="Foiz 24% yillik (qoldiqqa); asosiy qarz — Kontragentlar saldosining oylik kamayishi.",
        source="Kontragentlar (Bank krediti, oylik saldo), Kassa (kredit to'lovlari), prognoz",
        live=live,
        ctx=ctx,
        facts_out={
            "next": M(nx.amount),
            "date": nx.date.isoformat(),
            "cash_then": M(k),
            "balance": M(bal),
        },
    )


# --- N42 next_month_forecast -------------------------------------------------------------------
@register("next_month_forecast")
def next_month_forecast(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    base, s = f["base"], f["s"]
    t = f["today"]
    mstart = date(t.year + (t.month // 12), t.month % 12 + 1, 1)
    mdays = [
        mstart + timedelta(days=i) for i in range(calendar.monthrange(mstart.year, mstart.month)[1])
    ]
    rev = D0
    daily = []
    for d in mdays:
        i = (d - base.today).days
        if 0 <= i < len(base.revenue):
            v = Decimal(int(base.revenue[i])) / 100
            rev += v
            daily.append((d, v))
    lm = last_month(s) if s.get("last_date") else None
    be = break_even(s, lm) if lm and (s.get("reports") or {}).get("pl") else None
    profit = (rev * be.cm_ratio - be.fixed).quantize(Decimal(1)) if be else D0
    acc = f["accuracy"].get("median_pct")
    err = _d(acc) / 100 if acc else Decimal("0.1")
    lo, hi = rev * (1 - err), rev * (1 + err)
    mon = f"{uz.MONTHS[mstart.month - 1]} {mstart.year}"
    verdict = f"{mon.capitalize()}: tushum ~{M(rev)} ({M(lo)}–{M(hi)}), foyda ~{M(profit)}. Aniqlik: o'tgan oylarda ±{str((err * 100).quantize(Decimal('0.1'))).replace('.', ',')}%."
    weeks: dict[int, Decimal] = {}
    for d, v in daily:
        weeks[(d.day - 1) // 7 + 1] = weeks.get((d.day - 1) // 7 + 1, D0) + v
    prev_rev = pl_value(s, "sof tushum", lm) if lm else D0
    live = f"{mon.capitalize()}da tushum taxminan {say_mln(rev)}, foyda {say_mln(profit)} bo'ladi."
    return card(
        item,
        verdict,
        [
            ("Tushum prognozi", M(rev), f"{M(lo)}–{M(hi)}", ""),
            (
                "Foyda prognozi",
                M(profit),
                "marjinal foyda − doimiy",
                "good" if profit > 0 else "bad",
            ),
            (
                "Aniqlik",
                f"±{str((err * 100).quantize(Decimal('0.1'))).replace('.', ',')}%",
                "backtest",
                "",
            ),
        ],
        chart={
            "title": f"{mon}: kunlik tushum prognozi (mln so'm)",
            "type": "line_multi",
            "unit": "mln so'm",
            "x_labels": [d.strftime("%d.%m.%Y") for d, _ in daily],
            "series": [
                {
                    "name": "Tushum",
                    "color": "#14B8A6",
                    "data": [float((v / 1_000_000).quantize(Decimal("0.01"))) for _, v in daily],
                }
            ],
        },
        table=(
            [
                "Hafta",
                "Tushum",
                f"Farq ({uz.MONTHS[int(lm[5:7]) - 1] if lm else ''} o'rtacha haftasiga)",
            ],
            [
                [
                    f"{w}-hafta",
                    N(v),
                    ("+" if v - prev_rev / Decimal("4.35") >= 0 else "")
                    + N(v - prev_rev / Decimal("4.35")),
                ]
                for w, v in sorted(weeks.items())
            ],
        ),
        assumptions="Kunlik model: trend × hafta kuni profili; foyda = tushum × marjinal foyda ulushi − doimiy xarajat (oxirgi yopilgan oy).",
        source="Smena (trend, hafta kuni), Foyda-zarar (xarajat ulushlari)",
        live=live,
        ctx=ctx,
        facts_out={"revenue": M(rev), "profit": M(profit)},
    )


# --- N43 break_even ----------------------------------------------------------------------------
@register("break_even")
def break_even_cat(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    be = break_even(s, lm)
    c_be, c_now = (
        be.be_checks_per_day.quantize(Decimal(1), ROUND_HALF_UP),
        be.checks_per_day.quantize(Decimal(1), ROUND_HALF_UP),
    )
    margin = (
        ((be.checks_per_day - be.be_checks_per_day) / be.checks_per_day)
        if be.checks_per_day
        else D0
    )
    verdict = f"Zararsizlik: oyiga {M(be.be_revenue)} = kuniga {N(c_be)} chek. Hozir {N(c_now)} — {(margin * 100).quantize(Decimal(1))!s}% yuqori."
    live = f"Kuniga {uz.uz_number_words(int(c_be))} ta chek zararsizlik; hozir {uz.uz_number_words(int(c_now))} ta — {'xavfsiz' if margin > Decimal('0.15') else 'chegaraga yaqin'}."
    sd = (s.get("details") or {}).get("smena_days") or []
    last60 = sd[-60:]
    chart = {
        "title": "Kunlik cheklar + zararsizlik chizig'i",
        "type": "line_multi",
        "x_labels": [x[0][8:10] + "." + x[0][5:7] + "." + x[0][:4] for x in last60],
        "series": [
            {"name": "Cheklar", "color": "#14B8A6", "data": [float(_d(x[1])) for x in last60]}
        ],
        "ref_lines": [{"y": float(c_be), "label": "Zararsizlik", "color": "#DC2626"}],
    }
    return card(
        item,
        verdict,
        [
            ("Zararsizlik (chek/kun)", N(c_be), f"{M(be.be_revenue)}/oy", ""),
            ("Hozir", N(c_now), f"o'rtacha chek {M(be.avg_check)}", "good"),
            (
                "Xavfsizlik zaxirasi",
                f"{(margin * 100).quantize(Decimal(1))!s}%",
                "",
                "good" if margin > Decimal("0.15") else "bad",
            ),
        ],
        chart=chart,
        table=(
            ["Ko'rsatkich", "Qiymat"],
            [
                ["Doimiy xarajat", N(be.fixed)],
                [
                    "Marjinal foyda ulushi",
                    f"{str((be.cm_ratio * 100).quantize(Decimal('0.1'))).replace('.', ',')}%",
                ],
                ["Zararsizlik tushumi", N(be.be_revenue)],
                [
                    "Pul oqimi zararsizligi (kredit bilan)",
                    f"{N(be.cash_be_checks_per_day)} chek/kun",
                ],
            ],
        ),
        assumptions="Zararsizlik = doimiy xarajat ÷ marjinal foyda ulushi; chek/kun = ÷ o'rtacha chek ÷ kunlar.",
        source=f"Foyda-zarar ({lm}), Smena (o'rtacha chek)",
        live=live,
        ctx=ctx,
        facts_out={"be_checks": N(c_be), "now_checks": N(c_now), "be_revenue": M(be.be_revenue)},
    )


# --- N53 weekly_health / N57 daily_brief ---------------------------------------------------------
def _daily_sales() -> dict[date, Decimal]:
    from django.db.models import Sum

    from apps.finance.models import Transaction

    rows = (
        Transaction.objects.filter(is_actual=True, direction="in", category="savdo")
        .values("txn_date")
        .annotate(s=Sum("amount"))
    )
    return {r["txn_date"]: _d(r["s"]) for r in rows}


@register("weekly_health")
def weekly_health(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    sales = _daily_sales()
    if not sales:
        return card(
            item,
            "Kunlik savdo ma'lumoti topilmadi — Smena varag'ini to'ldiring.",
            [
                ("Haftalik tushum", "—", "", ""),
                ("O'tgan haftaga", "—", "", ""),
                ("Kassa", M(f["cash"]), "", ""),
            ],
            ctx=ctx,
        )
    last = max(sales)
    wk = [last - timedelta(days=i) for i in range(6, -1, -1)]
    prev = [d - timedelta(days=7) for d in wk]
    t1, t0 = sum((sales.get(d, D0) for d in wk), D0), sum((sales.get(d, D0) for d in prev), D0)
    pct = ((t1 / t0 - 1) * 100).quantize(Decimal(1)) if t0 else D0
    sd = {x[0]: _d(x[1]) for x in ((f["s"].get("details") or {}).get("smena_days") or [])}
    ch1, ch0 = (
        sum((sd.get(d.isoformat(), D0) for d in wk), D0),
        sum((sd.get(d.isoformat(), D0) for d in prev), D0),
    )
    signals = []
    if ch0 and (ch1 / ch0 - 1) < Decimal("-0.05"):
        signals.append(f"Cheklar {((ch1 / ch0 - 1) * 100).quantize(Decimal(1))!s}% kamaydi")
    if ch1 and ch0 and (t1 / ch1) > (t0 / ch0) * Decimal("1.03"):
        signals.append(f"O'rtacha chek oshdi: {N(t0 / ch0)} → {N(t1 / ch1)}")
    if f["min_balance"] < f["buffer"] * 2:
        signals.append(f"Eng tang kun {Dt(f['min_date'])}: {M(f['min_balance'])}")
    signals = signals or ["Katta og'ish yo'q"]
    nxt = [o for o in f["obligations"] if o.date <= f["today"] + timedelta(days=7)]
    verdict = f"Hafta ({Dt(wk[0])} – {Dt(wk[-1])}): tushum {M(t1)} ({'+' if pct >= 0 else ''}{pct}% o'tgan haftaga), kassa {M(f['cash'])}. Diqqat: {signals[0]}."
    live = f"Bu hafta {'yaxshi' if pct >= 0 else 'sustroq'} o'tdi — tushum o'tgan haftadan {uz.uz_number_words(int(abs(pct)))} foiz {'yuqori' if pct >= 0 else 'past'}."
    return card(
        item,
        verdict,
        [
            ("Haftalik tushum (kassaga)", M(t1), f"{N(ch1)} chek · agregatorsiz", ""),
            (
                "O'tgan haftaga",
                f"{'+' if pct >= 0 else ''}{pct}%",
                M(t0),
                "good" if pct >= 0 else "bad",
            ),
            ("Kassa", M(f["cash"]), "bugun", ""),
        ],
        chart={
            "title": "7 kun tushum (mln so'm)",
            "type": "bar",
            "x": "kun",
            "y": "qiymat",
            "unit": "so'm",
            "data": [
                {
                    "kun": f"{DAYS_UZ[d.weekday()][:2].capitalize()} {d.day}",
                    "qiymat": float(sales.get(d, D0)),
                    "color": "#14B8A6",
                }
                for d in wk
            ],
        },
        table=(
            ["Signal / to'lov", "Summa / izoh"],
            [[x, ""] for x in signals] + [[f"{Dt(o.date)} · {o.title}", N(o.amount)] for o in nxt],
        ),
        source="Smena (kunlik to'lovlar, cheklar), Kassa, prognoz",
        live=live,
        ctx=ctx,
        facts_out={"week": M(t1), "pct": str(pct)},
    )


@register("daily_brief")
def daily_brief(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    sales = _daily_sales()
    last = max(sales) if sales else f["today"]
    y = sales.get(last, D0)
    same = [sales.get(last - timedelta(days=7 * k), D0) for k in range(1, 5)]
    target = sum(same, D0) / len([x for x in same if x]) if any(same) else D0
    pct = (y / target * 100).quantize(Decimal(1)) if target else D0
    today_pays = [o for o in f["obligations"] if o.date <= f["today"] + timedelta(days=1)]
    signals = []
    if f["min_balance"] < f["buffer"] * 2:
        signals.append(f"Eng tang kun {Dt(f['min_date'])}: kassa {M(f['min_balance'])}")
    q = getattr(ctx.business, "data_quality", None) or {}
    if q.get("approximate"):
        signals.append("Prognoz taxminiy — " + (q.get("accuracy") or {}).get("text", ""))
    signals = signals or ["Katta signal yo'q"]
    action = (
        f"{today_pays[0].title} uchun {M(today_pays[0].amount)} tayyorlang"
        if today_pays
        else f"Kunlik maqsad: {M(target)} ({DAYS_UZ[(last + timedelta(days=1)).weekday()]})"
    )
    pays_txt = (
        ", ".join(f"{o.title.split(' · ')[0]} {M(o.amount)}" for o in today_pays)
        or "majburiy to'lov yo'q"
    )
    verdict = f"Kecha ({Dt(last)}) {M(y)} ({pct}% maqsad). Kassa {M(f['cash'])}. Bugun: {pays_txt}. Diqqat: {signals[0]}."
    live = f"Xayrli tong! Kecha {'maqsad bajarildi' if pct >= 100 else 'maqsaddan biroz past'}, kassa {'yetarli' if f['cash'] > f['buffer'] else 'tang'}; bugun {pays_txt}."
    return card(
        item,
        verdict,
        [
            ("Kechagi tushum", M(y), f"{pct}% maqsad", "good" if pct >= 100 else "bad"),
            ("Kassa", M(f["cash"]), "bugun", ""),
            (
                "Bugungi to'lovlar",
                M(sum((_d(o.amount) for o in today_pays), D0)),
                f"{len(today_pays)} ta",
                "",
            ),
        ],
        table=(
            ["Signal", "Harakat"],
            [[x, ""] for x in signals] + [["Bugungi bitta harakat", action]],
        ),
        actions=[action, "Signalni tekshiring", "Kun oxirida maqsadni solishtiring"],
        source="Smena (kecha), Kassa, to'lov kalendari",
        live=live,
        ctx=ctx,
        facts_out={"yesterday": M(y), "pct": str(pct), "cash": M(f["cash"])},
    )

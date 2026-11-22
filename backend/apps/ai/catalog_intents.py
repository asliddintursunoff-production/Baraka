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


# ===================== batch 3: reserve, loans, financing =====================================
RATE = Decimal("0.24")


def fixed_month(s: dict[str, Any]) -> Decimal:
    lm = last_month(s)
    return break_even(s, lm).fixed if (s.get("reports") or {}).get("pl") else D0


def loan_schedule(
    bal: Decimal, principal: Decimal, start: date, extra: Decimal = D0, rate: Decimal = RATE
) -> list[tuple[date, Decimal, Decimal, Decimal]]:
    rows, b, i = [], bal, 0
    principal = principal or (bal / 24)
    while b > 0 and i < 240:
        mm = start.month - 1 + i
        d = date(start.year + mm // 12, mm % 12 + 1, min(start.day, 28))
        it = (b * rate / 12).quantize(Decimal(1))
        pr = min(b, principal + extra)
        b -= pr
        rows.append((d, pr, it, b))
        i += 1
    return rows


def annuity(p: Decimal, rate: Decimal, n: int) -> Decimal:
    r = rate / 12
    return (p * r / (1 - (1 + r) ** -n)).quantize(Decimal(1)) if r else (p / n).quantize(Decimal(1))


def irr_monthly(flows: list[Decimal]) -> Decimal:
    """Monthly rate r where NPV = 0 (flows from the borrower's view: +loan, −payments)."""
    lo, hi = Decimal("0"), Decimal("1")
    for _ in range(80):
        mid = (lo + hi) / 2
        npv = sum((cf / (1 + mid) ** t for t, cf in enumerate(flows)), D0)
        if npv < 0:  # payments still worth more than the loan: the rate is higher
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def op_cash_avg(s: dict[str, Any], n: int = 3) -> Decimal:
    act = (s.get("journals") or {}).get("activities") or {}
    lm = last_month(s)
    ms = sorted(k for k in act if k <= lm)[-n:]
    return sum((_d(act[k].get("operating")) for k in ms), D0) / len(ms) if ms else D0


def P(x: Decimal) -> str:
    return f"{str((x * 100).quantize(Decimal('0.1'))).replace('.', ',')}%"


@register("cash_reserve_target")
def cash_reserve(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    mn, rec = f["buffer"], fixed_month(f["s"])
    k = f["cash"]
    state = "yetarli" if k >= rec else ("minimaldan yuqori, tavsiyadan kam" if k >= mn else "kam")
    verdict = f"Minimal {M(mn)}, tavsiya {M(rec)}. Hozir {M(k)} — {state}."
    live = f"Kamida {say_mln(mn)}, yaxshisi {say_mln(rec)} tegmay turishi kerak."
    return card(
        item,
        verdict,
        [
            ("Minimal zaxira", M(mn), "7 kunlik majburiy chiqim", ""),
            ("Tavsiya zaxira", M(rec), "1 oylik doimiy xarajat", ""),
            ("Hozirgi kassa", M(k), state, "good" if k >= rec else "bad"),
        ],
        chart={"title": "Kassa va zaxira chegaralari", **cash_chart(f, 60)},
        table=(
            ["Zaxira", "Summa", "Nima uchun"],
            [
                ["Minimal", N(mn), "1 hafta majburiy to'lovlar"],
                ["Tavsiya", N(rec), "1 oy doimiy xarajat (savdo to'xtasa)"],
                ["Hozir", N(k), state],
            ],
        ),
        assumptions="Minimal = keyingi 30 kun majburiy to'lovlarining 7 kunligi; tavsiya = oxirgi yopilgan oy doimiy xarajati.",
        source="Foyda-zarar (doimiy xarajat), to'lov kalendari",
        live=live,
        ctx=ctx,
        facts_out={"min": M(mn), "rec": M(rec), "cash": M(k)},
    )


@register("shutdown_runway")
def closure_runway(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    obl30 = sum(
        (_d(o.amount) for o in f["obligations"] if o.date <= f["today"] + timedelta(days=30)), D0
    )
    daily = (obl30 / 30).quantize(Decimal(1))
    recv = sum(
        (
            -_d((b.get("months") or {}).get(f["today"].replace(day=1).isoformat(), b["balance"]))
            for b in (f["s"].get("details") or {}).get("counterparties") or []
            if "agregator" in str(b.get("type", "")).lower() and _d(b["balance"]) < 0
        ),
        D0,
    )
    days = int(((f["cash"] + recv) / daily).quantize(Decimal(1))) if daily else 0
    nclose = int(p.get("horizon_days") or 30)
    end = f["cash"] + recv - daily * nclose
    verdict = (
        f"Savdosiz {days} kun chidaysiz. {nclose} kun yopilsangiz, kassa {M(end)} gacha tushadi."
    )
    live = f"Savdo to'xtasa, pulingiz taxminan {uz.uz_number_words(days)} kunga yetadi."
    path = [f["cash"] + recv - daily * i for i in range(0, min(days + 5, 120))]
    return card(
        item,
        verdict,
        [
            ("Runway (kun)", str(days), "savdo nol bo'lsa", "good" if days >= 30 else "bad"),
            ("Kunlik doimiy chiqim", M(daily), "majburiy to'lovlar ÷ 30", ""),
            (
                "Yopilish oxirida kassa",
                M(end),
                f"{nclose} kundan keyin",
                "good" if end > 0 else "bad",
            ),
        ],
        chart={
            "title": "Savdosiz kassa yo'li (mln so'm)",
            "type": "line_multi",
            "unit": "mln so'm",
            "zero_line": True,
            "x_labels": [
                (f["today"] + timedelta(days=i)).strftime("%d.%m.%Y") for i in range(len(path))
            ],
            "series": [
                {
                    "name": "Kassa (savdosiz)",
                    "color": "#F87171",
                    "data": [float((v / 1_000_000).quantize(Decimal("0.1"))) for v in path],
                }
            ],
        },
        table=(
            ["Manba", "Summa"],
            [
                ["Kassa bugun", N(f["cash"])],
                ["Agregatorlardan keladi", N(recv)],
                ["Kunlik majburiy chiqim", N(daily)],
            ],
        ),
        assumptions="Savdo 0; agregatorlar qarzi tushadi; o'zgaruvchan xarajat (xomashyo) to'xtaydi, majburiy to'lovlar davom etadi.",
        source="Prognoz, Kontragentlar (agregator saldosi), to'lov kalendari",
        live=live,
        ctx=ctx,
        facts_out={"days": str(days), "daily": M(daily)},
    )


@register("supplier_terms_whatif")
def supplier_delay(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    weekly = (
        _d((s.get("months") or {}).get(lm, {}).get("supplier_payments")) / Decimal("4.35")
    ).quantize(Decimal(1))
    weeks = int(p.get("weeks") or 2)
    free = weekly * weeks
    a, b = f["min_balance"], f["min_balance"] + free
    verdict = f"Kassa bir martalik ~{M(free)} ga bo'shaydi; eng tang kun ({Dt(f['min_date'])}) {M(a)} → {M(b)}."
    live = f"Ikki hafta muddat kassangizga bir martalik {say_mln(free)} havo beradi."
    return card(
        item,
        verdict,
        [
            ("Bo'shaydigan pul", M(free), f"{weeks} hafta × {M(weekly)}", "good"),
            ("Eng tang kun (oldin/keyin)", f"{M(a)} → {M(b)}", Dt(f["min_date"]), ""),
            ("Xavf", "o'rta", "narx +2–3% yoki munosabat", ""),
        ],
        table=(
            ["Ko'rsatkich", "Qiymat"],
            [
                ["Haftalik to'lov ta'minotchilarga", N(weekly)],
                ["Kechiktirish", f"{weeks} hafta"],
                ["Bir martalik bo'shash", N(free)],
            ],
        ),
        actions=[
            "Asosiy ta'minotchi bilan 14 kunlik muddat kelishing",
            "Evaziga narxni qotirib oling (oshirmaslik)",
            "Bo'shagan pulni zaxiraga qo'ying, sarflamang",
        ],
        assumptions="Haftalik to'lov = oxirgi yopilgan oy ta'minotchilarga to'lovlar ÷ 4,35.",
        source=f"Kassa (yetkazib beruvchiga to'lov, {lm})",
        live=live,
        ctx=ctx,
        facts_out={"free": M(free)},
    )


@register("seasonal_cash_plan")
def low_season_plan(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    seas = {
        int(k): _d(v) for k, v in ((s.get("details") or {}).get("seasonality") or {}).items()
    } or {m: Decimal(1) for m in range(1, 13)}
    be = break_even(s, lm)
    base = be.revenue / seas.get(int(lm[5:7]), Decimal(1))
    rows, best = [], None
    for k in range(1, 7):
        mm = (f["today"].month - 1 + k) % 12 + 1
        yr = f["today"].year + (f["today"].month - 1 + k) // 12
        rev = base * seas.get(mm, Decimal(1))
        prof = rev * be.cm_ratio - be.fixed
        rows.append((mm, yr, rev, prof))
        if best is None or prof < best[3]:
            best = (mm, yr, rev, prof)
    avg_prof = sum((r[3] for r in rows), D0) / len(rows)
    need = sum((max(D0, avg_prof - r[3]) for r in rows if r[3] < avg_prof), D0).quantize(Decimal(1))
    mm, yr, rev, prof = best
    drop = (1 - rev / base) if base else D0
    verdict = f"{uz.MONTHS[mm - 1].capitalize()} {yr} eng past: tushum ~{P(drop)} kam, foyda ~{M(prof)}. Oldindan {M(need)} yig'ib qo'ying."
    live = f"{uz.MONTHS[mm - 1].capitalize()} eng past oy; oldindan {say_mln(need)} yig'ib qo'ysangiz, bemalol o'tasiz."
    return card(
        item,
        verdict,
        [
            (
                "Eng past oy",
                f"{uz.MONTHS[mm - 1].capitalize()} {yr}",
                f"koeff. {seas.get(mm)}",
                "bad",
            ),
            ("Foyda o'sha oyda", M(prof), "", "bad" if prof < 0 else ""),
            ("Oldindan yig'ish", M(need), "past oylar uchun", ""),
        ],
        chart={
            "title": "Keyingi 6 oy: tushum va foyda (mln so'm)",
            "type": "bar_grouped",
            "x": "label",
            "unit": "mln so'm",
            "group_colors": {"tushum": "#94A3B8", "foyda": "#14B8A6"},
            "data": [
                {
                    "label": f"{uz.MONTHS[r[0] - 1][:3]} {r[1]}",
                    "tushum": float((r[2] / 1_000_000).quantize(Decimal("0.1"))),
                    "foyda": float((r[3] / 1_000_000).quantize(Decimal("0.1"))),
                }
                for r in rows
            ],
        },
        table=(
            ["Oy", "Mavsum koeff.", "Tushum", "Foyda"],
            [
                [f"{uz.MONTHS[r[0] - 1]} {r[1]}", str(seas.get(r[0])), N(r[2]), N(r[3])]
                for r in rows
            ],
        ),
        assumptions="Tushum = oxirgi oy (mavsumdan tozalangan) × Fin reja mavsum koeffitsienti; foyda = tushum × marjinal ulush − doimiy.",
        source="Fin reja (mavsumiylik), Foyda-zarar",
        live=live,
        ctx=ctx,
        facts_out={"low": f"{mm}/{yr}", "need": M(need)},
    )


def _loan_or_missing(
    item: CatalogItem, f: dict[str, Any], ctx: ToolContext
) -> dict[str, Any] | None:
    if f["loan"]:
        return None
    return card(
        item,
        "Kreditingiz topilmadi (Kontragentlar varag'ida 'Bank krediti' saldosi yo'q). Kredit summasi, foizi va muddatini ayting — darhol hisoblayman.",
        [("Qoldiq", "—", "", ""), ("Foiz", "—", "", ""), ("Kassa", M(f["cash"]), "", "")],
        ctx=ctx,
    )


@register("loan_prepay")
def loan_prepay(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    miss = _loan_or_missing(item, f, ctx)
    if miss:
        return miss
    bal, pr = f["loan"]["balance"], f["loan"]["principal"]
    start = next(
        (o.date for o in f["obligations"] if o.category == "loan"), f["today"] + timedelta(days=30)
    )
    rec0 = fixed_month(f["s"])
    default = f["cash"] - rec0 if f["cash"] - rec0 > 1_000_000 else f["cash"] - f["buffer"]
    amt = min(bal, _d(p.get("amount")) if p.get("amount") else max(D0, default))
    old = loan_schedule(bal, pr, start)
    new = loan_schedule(bal - amt, pr, start) if bal > amt else []
    save = sum((r[2] for r in old), D0) - sum((r[2] for r in new), D0)
    after = f["cash"] - amt
    rec = fixed_month(f["s"])
    verdict = (
        f"{M(amt)} oldin yopsangiz ~{M(save)} foiz tejaysiz; lekin kassa {M(after)} ga tushadi"
        + (f" — tavsiya zaxiradan ({M(rec)}) past." if after < rec else ".")
    )
    live = "Kreditni oldin yopish foizdan tejaydi" + (
        ", lekin avval zaxirani to'ldiring." if after < rec else " va kassa xavfsiz qoladi."
    )
    return card(
        item,
        verdict,
        [
            ("Foiz tejovi", M(save), f"{len(old)} oylik jadval bo'yicha", "good"),
            (
                "Kassa keyin",
                M(after),
                f"zaxira tavsiyasi {M(rec)}",
                "good" if after >= rec else "bad",
            ),
            ("Kredit stavkasi", "24%", "muqobil daromad shundan yuqorimi?", ""),
        ],
        table=(
            ["Ko'rsatkich", "Hozirgi jadval", "Oldin yopsa"],
            [
                ["Qolgan oylar", str(len(old)), str(len(new))],
                ["Qolgan foiz", N(sum((r[2] for r in old), D0)), N(sum((r[2] for r in new), D0))],
            ],
        ),
        actions=[
            "Avval zaxirani (1 oy doimiy xarajat) to'ldiring",
            f"Keyin bo'sh pul bilan qisman yoping (masalan {M(min(amt, max(D0, f['cash'] - rec)))})",
            "Bank bilan muddatidan oldin to'lash shartini yozma kelishing",
        ],
        assumptions="Foiz 24% yillik qoldiqqa; asosiy qarz oyiga teng ulushda.",
        source="Kontragentlar (Bank krediti), Foyda-zarar (foiz)",
        live=live,
        ctx=ctx,
        facts_out={"save": M(save), "after": M(after)},
        plan="Kreditni oldin yopish: zaxira to'lgach bank bilan kelishish",
    )


@register("loan_payoff_timeline")
def loan_payoff_date(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    miss = _loan_or_missing(item, f, ctx)
    if miss:
        return miss
    bal, pr = f["loan"]["balance"], f["loan"]["principal"]
    start = next(
        (o.date for o in f["obligations"] if o.category == "loan"), f["today"] + timedelta(days=30)
    )
    sch = loan_schedule(bal, pr, start)
    fast = loan_schedule(bal, pr, start, extra=Decimal(5_000_000))
    rest = sum((r[2] for r in sch), D0)
    end = sch[-1][0]
    verdict = f"Qoldiq {M(bal)}; {Dt(end)}da yopiladi, yana {M(rest)} foiz to'laysiz."
    live = f"Kreditingiz {uz.MONTHS[end.month - 1]} {end.year}da tugaydi; har oy qo'shimcha besh million bersangiz, {len(sch) - len(fast)} oy erta."
    return card(
        item,
        verdict,
        [
            ("Qoldiq", M(bal), f["loan"]["name"], ""),
            ("Yopilish sanasi", Dt(end), f"{len(sch)} oy", ""),
            ("Qolgan foiz", M(rest), "24% yillik", "bad"),
        ],
        chart={
            "title": "Qoldiq: hozirgi jadval vs +5 mln/oy (mln so'm)",
            "type": "line_multi",
            "unit": "mln so'm",
            "x_labels": [r[0].strftime("%m.%Y") for r in sch],
            "series": [
                {
                    "name": "Hozirgi jadval",
                    "color": "#94A3B8",
                    "data": [float((r[3] / 1_000_000).quantize(Decimal("0.1"))) for r in sch],
                },
                {
                    "name": "+5 mln/oy",
                    "color": "#14B8A6",
                    "data": [
                        float((fast[i][3] / 1_000_000).quantize(Decimal("0.1")))
                        if i < len(fast)
                        else 0
                        for i in range(len(sch))
                    ],
                },
            ],
        },
        table=(
            ["Sana", "Asosiy", "Foiz", "Qoldiq"],
            [[Dt(r[0]), N(r[1]), N(r[2]), N(r[3])] for r in sch[:12]],
        ),
        assumptions="Asosiy qarz — Kontragentlar saldosining oylik kamayishi; foiz 24% yillik.",
        source="Kontragentlar (Bank krediti, oylik saldo)",
        live=live,
        ctx=ctx,
        facts_out={"end": end.isoformat(), "interest": M(rest), "months": str(len(sch))},
    )


@register("loan_whatif")
def loan_affordability_cat(
    ctx: ToolContext, item: CatalogItem, p: dict[str, Any]
) -> dict[str, Any]:
    f = facts(ctx)
    amt = _d(p.get("amount") or 100_000_000)
    n = int(p.get("months") or 12)
    pay = annuity(amt, RATE, n)
    over = pay * n - amt
    cur = (f["loan"]["principal"] + (f["loan"]["balance"] * RATE / 12)) if f["loan"] else D0
    ocf = op_cash_avg(f["s"]) + cur  # operating cash before current debt service
    dscr = (ocf / (cur + pay)).quantize(Decimal("0.01")) if (cur + pay) else D0
    ok = dscr >= Decimal("1.25")
    verdict = f"{M(amt)}, {n} oy, 24%: oyiga {M(pay)}. DSCR {str(dscr).replace('.', ',')}x — {'ko‘tara olasiz' if ok else 'xavfli'}."
    live = f"{say_mln(amt).capitalize()} kreditga oyiga {say_mln(pay)}ga yaqin to'laysiz — {'biznes ko‘taradi' if ok else 'biznes uchun og‘ir'}."
    return card(
        item,
        verdict,
        [
            ("Oylik to'lov", M(pay), f"{n} oy annuitet", ""),
            ("Jami ortiqcha", M(over), "foiz", "bad"),
            (
                "DSCR",
                f"{str(dscr).replace('.', ',')}x",
                "≥ 1,25 — xavfsiz",
                "good" if ok else "bad",
            ),
        ],
        table=(
            ["Ko'rsatkich", "Qiymat"],
            [
                ["Operatsion pul oqimi (o'rtacha, kreditdan oldin)", N(ocf)],
                ["Hozirgi kredit to'lovi", N(cur)],
                ["Yangi kredit to'lovi", N(pay)],
                [
                    "Eng tang kun kassasi (yangi kreditsiz)",
                    f"{N(f['min_balance'])} ({Dt(f['min_date'])})",
                ],
            ],
        ),
        actions=[
            "Kredit nimaga olinishini aniqlang (foyda keltiradimi?)"
            if not p.get("purpose")
            else "Kredit maqsadi bo'yicha qoplash hisobini ko'ring",
            "DSCR 1,25x dan past bo'lsa — summani kamaytiring yoki muddatni uzaytiring",
            "Bir necha bank takliflarini solishtiring",
        ],
        assumptions="DSCR = oxirgi 3 oy o'rtacha operatsion pul oqimi ÷ (hozirgi + yangi kredit to'lovi).",
        source="Pul oqimi (operatsion), Kontragentlar (kredit)",
        live=live,
        ctx=ctx,
        facts_out={"pay": M(pay), "dscr": str(dscr), "over": M(over)},
    )


def _offers(amt: Decimal) -> list[tuple[str, Decimal, Decimal, int, list[Decimal]]]:
    """(name, upfront, monthly, months, cash flows from the buyer's view for IRR)."""
    k = annuity(amt, RATE, 12)
    lease_m = annuity(amt * Decimal("0.8"), Decimal("0.28"), 24)
    inst_m = (amt * Decimal("0.8") * (1 + Decimal("0.2") * 6 / 12) / 6).quantize(Decimal(1))
    return [
        ("Bank krediti (24%, 12 oy)", D0, k, 12, [amt] + [-k] * 12),
        (
            "Lizing (20% + 24 oy, ~28%)",
            amt * Decimal("0.2"),
            lease_m,
            24,
            [amt * Decimal("0.8")] + [-lease_m] * 24,
        ),
        (
            "Muddatli to'lov (20% + 6 oy, ~20% ustama)",
            amt * Decimal("0.2"),
            inst_m,
            6,
            [amt * Decimal("0.8")] + [-inst_m] * 6,
        ),
    ]


@register("financing_compare")
def financing_compare(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    amt = _d(p.get("amount") or 50_000_000)
    rows = []
    for name, up, m, n, flows in _offers(amt):
        over = up + m * n - amt
        eff = (1 + irr_monthly(flows)) ** 12 - 1
        rows.append((name, up, m, n, over, eff))
    best = min(rows, key=lambda r: r[5])
    verdict = (
        f"Eng arzon — {best[0].split(' (')[0]}: jami ortiqcha {M(best[4])}, effektiv {P(best[5])}."
    )
    live = f"Bu summaga eng arzoni {best[0].split(' (')[0].lower()} — ortiqcha to'lov eng kam."
    return card(
        item,
        verdict,
        [
            ("Eng arzon", best[0].split(" (")[0], "", "good"),
            ("Ortiqcha to'lov", M(best[4]), "", ""),
            ("Effektiv stavka", P(best[5]), "yillik", ""),
        ],
        table=(
            ["Variant", "Boshlang'ich", "Oyiga", "Muddat", "Ortiqcha", "Effektiv yillik"],
            [[r[0], N(r[1]), N(r[2]), f"{r[3]} oy", N(r[4]), P(r[5])] for r in rows],
        ),
        assumptions="Lizing va muddatli to'lov shartlari — bozor taxmini (taklifingiz bo'lsa, raqamlarini ayting). Effektiv stavka — to'lovlar oqimining IRR'i.",
        source="Bozor taxminlari, kredit 24%",
        live=live,
        ctx=ctx,
        facts_out={"best": best[0], "eff": P(best[5])},
    )


@register("installment_true_rate")
def installment_real_rate(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    amt = _d(p.get("amount") or 25_000_000)
    up_pct, n, markup = (
        Decimal(str(p.get("upfront_pct") or 20)) / 100,
        int(p.get("months") or 6),
        Decimal(str(p.get("markup_pct") or 20)) / 100,
    )
    fin = amt * (1 - up_pct)
    m = (fin * (1 + markup * n / 12) / n).quantize(Decimal(1))
    over = m * n - fin
    eff = (1 + irr_monthly([fin] + [-m] * n)) ** 12 - 1
    k_over = annuity(fin, RATE, n) * n - fin
    cheaper = eff < RATE
    verdict = (
        f"Haqiqiy stavka ~{P(eff)} yillik — kredit (24%) dan {'arzon' if cheaper else 'qimmat'}."
    )
    live = f"Bu bo'lib to'lash aslida yillik {uz.uz_number_words(int((eff * 100).quantize(Decimal(1))))} foiz — kreditdan {'arzon' if cheaper else 'qimmat'}."
    return card(
        item,
        verdict,
        [
            ("Effektiv stavka", P(eff), "yillik (IRR)", "good" if cheaper else "bad"),
            ("Ortiqcha to'lov", M(over), f"{n} oyda", ""),
            ("Kredit bilan farq", M(over - k_over), "+ — qimmat", ""),
        ],
        table=(
            ["Ko'rsatkich", "Muddatli to'lov", f"Kredit 24%, {n} oy"],
            [
                ["Boshlang'ich", N(amt * up_pct), "0"],
                ["Oyiga", N(m), N(annuity(fin, RATE, n))],
                ["Ortiqcha", N(over), N(k_over)],
            ],
        ),
        assumptions=f"Shartlar: {int(up_pct * 100)}% boshlang'ich, {n} oy, ustama {int(markup * 100)}% yillik (oddiy). O'zgartirsangiz, qayta hisoblanadi.",
        source="Taklif shartlari",
        live=live,
        ctx=ctx,
        facts_out={"eff": P(eff), "over": M(over)},
    )


@register("deposit_vs_business")
def deposit_vs_business(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    amt = _d(p.get("amount") or 50_000_000)
    dep = (amt * Decimal("0.20") * Decimal("0.9")).quantize(
        Decimal(1)
    )  # ~20% deposit, 10% tax (taxmin)
    kredit = (min(amt, f["loan"]["balance"]) * RATE).quantize(Decimal(1)) if f["loan"] else D0
    lm = last_month(s)
    net = pl_value(s, "sof foyda", lm)
    assets = _d(((s.get("reports") or {}).get("balans") or {}).get("jami aktivlar", {}).get(lm))
    roic = (net * 12 / assets) if assets else D0
    biz = (amt * roic).quantize(Decimal(1))
    opts = sorted(
        [("Kreditni yopish", kredit), ("Biznesda aylantirish", biz), ("Depozit", dep)],
        key=lambda x: -x[1],
    )
    verdict = f"{M(amt)}: depozit ~{M(dep)}/yil, kreditni yopish {M(kredit)}/yil tejaydi, biznes ~{M(biz)}/yil ({P(roic)} ROIC). Eng yaxshi — {opts[0][0].lower()}."
    live = f"Bo'sh pulni depozitga qo'ygandan ko'ra, {opts[0][0].lower()} ko'proq foyda beradi."
    return card(
        item,
        verdict,
        [
            ("Depozit daromadi", M(dep), "~20%, soliqdan keyin (taxmin)", ""),
            (
                "Kredit tejovi",
                M(kredit),
                "24% yillik",
                "good" if opts[0][0] == "Kreditni yopish" else "",
            ),
            ("Biznes ROIC", P(roic), f"{M(biz)}/yil", ""),
        ],
        table=(["Variant", "Yillik foyda"], [[o[0], N(o[1])] for o in opts]),
        assumptions="Depozit ~20% yillik (taxmin, bank taklifini ayting); ROIC = yillik sof foyda ÷ jami aktivlar (Balans).",
        source=f"Balans, Foyda-zarar ({lm}), Kontragentlar (kredit)",
        live=live,
        ctx=ctx,
        facts_out={"best": opts[0][0]},
    )


@register("owner_withdrawal")
def owner_draw(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    ocf = op_cash_avg(s)
    prin = f["loan"]["principal"] if f["loan"] else D0
    rec = fixed_month(s)
    topup = max(D0, (rec - f["cash"]) / 6)
    free = max(D0, ocf - prin - topup).quantize(Decimal(1))
    pl = (s.get("reports") or {}).get("pl") or {}
    lm = last_month(s)
    a, b = (
        _d(pl.get("sherik 1 foyda ulushi", {}).get(lm)),
        _d(pl.get("sherik 2 foyda ulushi", {}).get(lm)),
    )
    sh1 = (a / (a + b)) if (a + b) else Decimal("0.5")
    verdict = f"Oyiga {M(free)} gacha olish xavfsiz (Sherik 1 — {M(free * sh1)}, Sherik 2 — {M(free * (1 - sh1))})."
    live = f"Oyiga {say_mln(free)}gacha olsangiz biznesga zarar qilmaydi."
    return card(
        item,
        verdict,
        [
            ("Xavfsiz summa", M(free), "oyiga", "good"),
            ("Bo'sh pul oqimi", M(ocf - prin), "operatsion − kredit asosiy", ""),
            (
                "Zaxira holati",
                "to'la" if f["cash"] >= rec else f"{M(rec - f['cash'])} kam",
                f"tavsiya {M(rec)}",
                "good" if f["cash"] >= rec else "bad",
            ),
        ],
        table=(
            ["Hisob", "Oyiga"],
            [
                ["Operatsion pul oqimi (3 oy o'rtacha)", N(ocf)],
                ["− Kredit asosiy qarz", N(prin)],
                ["− Zaxirani to'ldirish (6 oyda)", N(topup)],
                ["= Xavfsiz olish", N(free)],
            ],
        ),
        assumptions="Sheriklar ulushi Foyda-zarar 'Sherik foyda ulushi' qatorlaridan; kapital xarajat rejasi 0.",
        source="Pul oqimi, Kontragentlar, Foyda-zarar",
        live=live,
        ctx=ctx,
        facts_out={"free": M(free)},
    )


@register("overdraft_line")
def overdraft_value(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    short = [
        (d, f["buffer"] - f["close"][d]) for d in f["days"][:90] if f["close"][d] < f["buffer"]
    ]
    days = len(short)
    cost = (sum((x for _, x in short), D0) * RATE / 365).quantize(Decimal(1))
    limit = max((x for _, x in short), default=D0)
    commission = (limit * Decimal("0.01")).quantize(Decimal(1))
    yearly = (cost + commission) * 4
    worth = days > 0
    verdict = (
        f"Yiliga ~{days * 4} kun kerak bo'ladi, xarajati ~{M(yearly)}; {'arziydi (kichik limit ' + M(limit) + ')' if worth else 'arzimaydi'}."
        if worth
        else f"Keyingi 90 kunda kassa chegaradan pastga tushmaydi — overdraft kerak emas; zaxira {M(f['buffer'])} yetarli."
    )
    live = (
        "Overdraft faqat bir necha kunda kerak bo'ladi — kichik limit yetarli."
        if worth
        else "Overdraft hozir kerak emas — kassangiz chegaradan tushmaydi."
    )
    return card(
        item,
        verdict,
        [
            ("Kerakli kunlar", str(days), "90 kunda", ""),
            ("Yillik xarajat", M(yearly), "foiz + komissiya", ""),
            ("Muqobil (zaxira)", M(f["buffer"]), "7 kunlik", ""),
        ],
        chart={"title": "90 kunlik kassa va chegara", **cash_chart(f, 90)},
        assumptions="Overdraft 24% yillik + 1% komissiya limitdan (taxmin).",
        source="Kunlik prognoz",
        live=live,
        ctx=ctx,
        facts_out={"days": str(days), "yearly": M(yearly)},
    )

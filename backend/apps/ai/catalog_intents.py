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


# ===================== batch 4: capital decisions, price & menu what-ifs ========================
def menu_rows(s: dict[str, Any]) -> list[dict[str, Any]]:
    lm = last_month(s)
    out = []
    for n, d in ((s.get("details") or {}).get("menu") or {}).items():
        price, cost = _d(d.get("price")), _d(d.get("cost"))
        if price > 0:
            out.append(
                {
                    "name": n,
                    "price": price,
                    "cost": cost,
                    "margin": price - cost,
                    "fc": cost / price,
                    "sold": _d((d.get("sold") or {}).get(lm)),
                    "cat": d.get("category", ""),
                }
            )
    return out


def find_dish(s: dict[str, Any], text: str, default_word: str = "lavash") -> dict[str, Any] | None:
    rows = menu_rows(s)
    t = (text or "").lower()
    hit = next(
        (r for r in sorted(rows, key=lambda r: -len(r["name"])) if r["name"].lower() in t), None
    )
    if hit is None:
        word = next(
            (
                w
                for w in (
                    "lavash",
                    "burger",
                    "shaurma",
                    "hot-dog",
                    "fri",
                    "choy",
                    "ichimlik",
                    "kombo",
                    "naggets",
                )
                if w in t
            ),
            default_word,
        )
        cands = [r for r in rows if word in r["name"].lower()]
        hit = (
            max(cands, key=lambda r: r["sold"])
            if cands
            else (max(rows, key=lambda r: r["sold"]) if rows else None)
        )
    return hit


ELASTICITY = Decimal(
    "-0.8"
)  # fast-food price elasticity (taxmin; Lazzat Sep price rise: checks −3% at +4% price)


@register("capital_allocation")
def capital_allocation(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    amt = _d(p.get("amount") or 50_000_000)
    rec = fixed_month(s)
    a = min(amt, max(D0, rec - f["cash"]))  # 1) reserve gap
    rest = amt - a
    b = min(rest, f["loan"]["balance"]) if f["loan"] else D0  # 2) debt at 24% — guaranteed return
    b = min(b, rest * Decimal("0.5"))
    c = rest - b  # 3) best project (upsell / lunch set — Q4 levers; equipment → Q3)
    yearly = (b * RATE + c * Decimal("0.6")).quantize(Decimal(1))
    verdict = f"{M(amt)}: {M(a)} zaxiraga, {M(b)} kreditga, {M(c)} eng foydali loyihaga (qo'shimcha sotuv / lanch-set) — yillik ~{M(yearly)} foyda."
    live = f"{say_mln(amt).capitalize()}ni bunday bo'ling: zaxira, kredit va eng foydali loyiha."
    return card(
        item,
        verdict,
        [
            ("Eng yuqori daromad", "Loyiha (~60%/yil)", "taxmin", "good"),
            ("Taqsimot", f"{M(a)} / {M(b)} / {M(c)}", "zaxira / kredit / loyiha", ""),
            ("Yillik natija", M(yearly), "", "good"),
        ],
        table=(
            ["Yo'nalish", "Summa", "Yillik daromad", "Xavf"],
            [
                ["Zaxira (kassa)", N(a), "0 (xavfsizlik)", "yo'q"],
                ["Kreditni yopish (24%)", N(b), N(b * RATE), "yo'q"],
                ["Loyiha (qo'shimcha sotuv, lanch-set)", N(c), N(c * Decimal("0.6")), "o'rta"],
            ],
        ),
        actions=[
            "Avval zaxira (1 oylik doimiy xarajat) to'lsin",
            "Keyin 24% li kreditni qisman yoping — kafolatli daromad",
            "Qolganini tez qoplanadigan loyihaga; jihoz bo'lsa → «Apparat olsam-chi?» (Q3)",
        ],
        assumptions="Loyiha daromadi ~60%/yil (Q4 richaglari tajribasi, taxmin). Tartib: zaxira → qimmat qarz → loyiha.",
        source="Kassa, Kontragentlar (kredit), Foyda-zarar",
        live=live,
        ctx=ctx,
        facts_out={"reserve": M(a), "loan": M(b), "project": M(c)},
    )


@register("renovation_roi")
def renovation_roi(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    cost = _d(p.get("amount") or 30_000_000)
    hall = _d(
        (((s.get("details") or {}).get("channels") or {}).get("months") or {})
        .get(lm, {})
        .get("Zal", {})
        .get("revenue")
    )
    hall = hall or pl_value(s, "sof tushum", lm) * Decimal("0.4")
    days_closed = int(p.get("days") or 5)
    be = break_even(s, lm)
    lost = (hall / 30 * days_closed * be.cm_ratio).quantize(Decimal(1))
    uplift = Decimal("0.05")
    gain = (hall * uplift * be.cm_ratio).quantize(Decimal(1))
    total = cost + lost
    pay = (total / gain).quantize(Decimal("0.1")) if gain else None
    verdict = f"{M(cost)} + yopilish {days_closed} kun ({M(lost)} yo'qotish); zal +5% bo'lsa {str(pay).replace('.', ',')} oyda qoplaydi."
    live = f"Remont zal savdosini besh foizga oshirsa, taxminan {uz.uz_number_words(int(pay or 0))} oyda o'zini oqlaydi."
    return card(
        item,
        verdict,
        [
            ("Jami xarajat", M(total), "remont + yopilish", ""),
            ("Oylik qo'shimcha foyda", M(gain), "zal +5% × marja", "good"),
            (
                "Qoplash",
                f"{str(pay).replace('.', ',')} oy",
                "",
                "good" if pay and pay < 24 else "bad",
            ),
        ],
        table=(
            ["Ko'rsatkich", "Qiymat"],
            [
                ["Zal savdosi (oy)", N(hall)],
                ["Marjinal foyda ulushi", P(be.cm_ratio)],
                ["Eng yaxshi oy", "fevral (eng past mavsum)"],
            ],
        ),
        actions=[
            "Remontni eng past oyga (fevral) rejalashtiring",
            "Yopilishni 3–5 kunga qisqartiring (bosqichma-bosqich)",
            "Remontdan keyin 2 oy zal savdosini solishtiring",
        ],
        assumptions="Zal savdosi +5% (taxmin, 5–8% oralig'i); yopilish kunlarida zal savdosi yo'qoladi.",
        source=f"Sotuv (Zal kanali, {lm}), Foyda-zarar",
        live=live,
        ctx=ctx,
        facts_out={"payback": str(pay)},
    )


@register("bulk_purchase")
def bulk_purchase(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    pur = (s.get("details") or {}).get("purchases") or {}
    name = next((n for n in pur if "go'sht" in n.lower()), next(iter(pur), ""))
    mo = (pur.get(name) or {}).get("months", {}).get(lm, {})
    month_amt = _d(mo.get("amount"))
    disc = Decimal("0.07")
    months = int(p.get("months") or 1)
    save = (month_amt * disc).quantize(Decimal(1))
    tied = (month_amt * months - month_amt / Decimal("4.35")).quantize(Decimal(1))
    days = int((tied / (save / 30)).quantize(Decimal(1))) if save else 0
    ok = f["min_balance"] - tied >= f["buffer"]
    verdict = (
        f"{name}ni {months} oylik olsangiz oyiga ~{M(save)} tejaysiz, {M(tied)} pul band bo'ladi."
    )
    live = f"{name.split()[0]}ni ulgurji olsangiz oyiga {say_mln(save)}ga yaqin tejaysiz."
    return card(
        item,
        verdict,
        [
            ("Oylik tejov", M(save), "7% chegirma (taxmin)", "good"),
            ("Band pul", M(tied), "qo'shimcha zaxira", ""),
            ("Qoplash (kun)", str(days), "band pul tejov bilan", ""),
        ],
        table=(
            ["Ko'rsatkich", "Qiymat"],
            [
                [f"{name} oylik xaridi ({lm})", N(month_amt)],
                [
                    "Eng tang kun kassasi (keyin)",
                    f"{N(f['min_balance'] - tied)} ({'xavfsiz' if ok else 'chegaradan past'})",
                ],
                ["Saqlash", "muzlatgich sig'imi + isrof xavfi"],
            ],
        ),
        assumptions="Ulgurji chegirma 7% (taxmin, ta'minotchidan so'rang); muzlatgich sig'imi yetarli.",
        source=f"Kirim ({name}, {lm}), prognoz",
        live=live,
        ctx=ctx,
        facts_out={"save": M(save), "tied": M(tied)},
    )


@register("partner_buyout")
def partner_buyout(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    pl = (s.get("reports") or {}).get("pl") or {}
    a, b = (
        _d(pl.get("sherik 1 foyda ulushi", {}).get(lm)),
        _d(pl.get("sherik 2 foyda ulushi", {}).get(lm)),
    )
    share = Decimal(str(p.get("share") or ((b / (a + b) * 100) if (a + b) else 40))) / 100
    net = pl_value(s, "sof foyda", lm)
    ms = sorted(k for k in (pl.get("sof foyda") or {}) if k <= lm)[-6:]
    avg = sum((_d(pl["sof foyda"][k]) for k in ms), D0) / len(ms) if ms else net
    year = avg * 12
    lo, hi = year * 2 * share, year * 4 * share
    share_profit = year * share
    yrs = ((lo + hi) / 2 / share_profit).quantize(Decimal("0.1")) if share_profit > 0 else None
    verdict = f"{int(share * 100)}% ulush ~{M(lo)}–{M(hi)}; u ulushning foydasi yiliga ~{M(share_profit)} → {str(yrs).replace('.', ',')} yilda qoplaydi."
    live = f"Sherigingiz ulushi taxminan {say_mln(lo)} dan {say_mln(hi)}gacha — {uz.uz_number_words(int(yrs or 0))} yilda qoplaydi."
    return card(
        item,
        verdict,
        [
            ("Ulush narxi", f"{M(lo)}–{M(hi)}", "yillik foyda × 2–4", ""),
            ("Yillik ulush foydasi", M(share_profit), f"{int(share * 100)}%", "good"),
            ("Qoplash", f"{str(yrs).replace('.', ',')} yil", "", ""),
        ],
        table=(
            ["Ko'rsatkich", "Qiymat"],
            [
                ["O'rtacha oylik sof foyda (6 oy)", N(avg)],
                ["Yillik foyda", N(year)],
                ["Baho (2–4× yillik foyda)", f"{N(year * 2)} – {N(year * 4)}"],
            ],
        ),
        assumptions="Kichik biznes bahosi = yillik sof foyda × 2–4 (taxmin); sherik ulushi Foyda-zarar 'Sherik foyda ulushi' nisbatidan.",
        source="Foyda-zarar (sof foyda, sheriklar ulushi)",
        live=live,
        ctx=ctx,
        facts_out={"lo": M(lo), "hi": M(hi)},
    )


@register("corporate_catering")
def corporate_catering(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    n = int(p.get("portions") or 50)
    dish = find_dish(s, "lavash tovuqli")
    price = dish["price"] * Decimal("0.9") if dish else Decimal(35_000)
    cost = dish["cost"] if dish else Decimal(10_000)
    unit = price - cost - Decimal(1500) - Decimal(2000)
    month = (unit * n * 22).quantize(Decimal(1))
    from apps.engine import hiring as HR

    h = HR.compute(s, HR.Params())
    cap_ok = h.weekday_checks + Decimal(n) / 3 <= 90 * Decimal("0.95")
    recv = (price * n * 22 / 2).quantize(Decimal(1))
    verdict = f"Kuniga {n} porsiya → oyiga +{M(month)} foyda; tushlik pikida quvvat {'yetadi' if cap_ok else 'yetmaydi'}."
    live = f"Kuniga {uz.uz_number_words(n)} porsiya korporativ buyurtma oyiga {say_mln(month)} foyda beradi."
    return card(
        item,
        verdict,
        [
            ("Oylik foyda", M(month), f"{n} porsiya × 22 ish kuni", "good"),
            (
                "Quvvat",
                "yetadi" if cap_ok else "yetmaydi",
                f"ish kunlari {N(h.weekday_checks)}/90 chek",
                "good" if cap_ok else "bad",
            ),
            ("Debitorlik", M(recv), "ofislar 2 haftada to'laydi", ""),
        ],
        table=(
            ["Porsiya", "So'm"],
            [
                ["Narx (10% korporativ chegirma)", N(price)],
                ["Tannarx", N(cost)],
                ["Qadoq + yetkazish", "3 500"],
                ["Porsiya foydasi", N(unit)],
            ],
        ),
        assumptions="Korporativ narx −10%, qadoq 1 500, yetkazish 2 000 so'm/porsiya; ofislar 2 hafta kechikib to'laydi (taxmin).",
        source="Menyu (tannarx), Smena (ish kunlari yuklamasi)",
        live=live,
        ctx=ctx,
        facts_out={"month": M(month)},
    )


@register("branch_readiness")
def branch_readiness(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    pl = (s.get("reports") or {}).get("pl") or {}
    ms = sorted(k for k in (pl.get("sof foyda") or {}) if k <= lm)[-3:]
    profits = [_d(pl["sof foyda"][k]) for k in ms]
    rec = fixed_month(s)
    stable = all(x > Decimal(10_000_000) for x in profits)
    reserve_ok = f["cash"] >= rec
    invest = Decimal(350_000_000)
    month_profit = (sum(profits, D0) / len(profits)) if profits else D0
    pay = (invest / month_profit).quantize(Decimal(1)) if month_profit > 0 else None
    ready = stable and reserve_ok
    cond = (
        ", ".join(
            x
            for x, ok in (
                ("3 oy foyda ≥ 10 mln", stable),
                ("zaxira ≥ 1 oy doimiy xarajat", reserve_ok),
            )
            if not ok
        )
        or "hammasi bajarilgan"
    )
    verdict = f"Hozir {'tayyor' if ready else 'tayyor emas'}: shart — {cond}. Ochish ~{M(invest)}, qoplash ~{pay} oy (ramp-up bilan ko'proq)."
    live = (
        "Ikkinchi filialga hali erta — avval uch oy barqaror foyda va zaxira kerak."
        if not ready
        else "Ikkinchi filialga tayyorsiz — moliyalash rejasini tuzamiz."
    )
    return card(
        item,
        verdict,
        [
            ("Investitsiya", M(invest), "birinchi filial tajribasi (taxmin)", ""),
            ("Qoplash", f"~{pay} oy", "joriy oylik foyda bilan", ""),
            ("Tayyorlik", "tayyor" if ready else "tayyor emas", cond, "good" if ready else "bad"),
        ],
        table=(["Oy", "Sof foyda"], [[k, N(v)] for k, v in zip(ms, profits, strict=False)]),
        assumptions="Investitsiya — Investitsiyalar varag'idagi boshlang'ich investitsiya darajasi (~345 mln); filial ramp-up 6 oy.",
        source="Foyda-zarar (3 oy), Kassa, Investitsiyalar",
        live=live,
        ctx=ctx,
        facts_out={"ready": str(ready)},
    )


@register("franchise_out")
def franchise_out(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    rev = pl_value(s, "sof tushum", lm)
    lump, roy = Decimal(30_000_000), Decimal("0.04")
    year = (lump + rev * Decimal("0.8") * roy * 12 - Decimal(6_000_000)).quantize(Decimal(1))
    verdict = f"Bitta franshiza yiliga ~{M(year)}; tayyorlik: retseptlar (Texkarta) bor, standartlar va brend hujjatlashtirilmagan."
    live = f"Bitta franshiza yiliga taxminan {say_mln(year)} beradi, lekin avval standartlarni hujjatlashtiring."
    return card(
        item,
        verdict,
        [
            ("Yillik daromad (1 ta)", M(year), "paushal + 4% royalti", "good"),
            ("Tayyorlik", "qisman", "retsept bor, standart yo'q", ""),
            ("Xavf", "brend sifati", "nazorat kerak", "bad"),
        ],
        table=(
            ["Manba", "Yiliga"],
            [
                ["Paushal (bir marta)", N(lump)],
                [
                    "Royalti 4% (franchayzi tushumi ~80% sizniki)",
                    N(rev * Decimal("0.8") * roy * 12),
                ],
                ["Qo'llab-quvvatlash xarajati", "−6 000 000"],
            ],
        ),
        assumptions="Paushal 30 mln, royalti 4%, franchayzi tushumi sizning 80% ingiz (taxmin).",
        source=f"Foyda-zarar ({lm}), Texkarta",
        live=live,
        ctx=ctx,
        facts_out={"year": M(year)},
    )


@register("single_item_price")
def single_item_price(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    d = find_dish(s, ctx.last_user_text or p.get("dish", ""))
    if d is None:
        return card(
            item,
            "Menyu topilmadi — taom nomi va narxini ayting.",
            [("—", "—", "", "")] * 3,
            ctx=ctx,
        )
    delta = _d(p.get("amount") or 2000)
    pct = delta / d["price"]
    vol = d["sold"] * (1 + ELASTICITY * pct)
    new_p = d["price"] + delta
    change = (vol * (new_p - d["cost"]) - d["sold"] * d["margin"]).quantize(Decimal(1))
    verdict = f"{d['name']} {N(d['price'])} → {N(new_p)}: oyiga {'+' if change >= 0 else ''}{M(change)} foyda, sotuv ~{P(ELASTICITY * pct)}."
    live = f"{d['name']} narxini {N(delta)} so'mga oshirsangiz, oyiga {say_mln(change)} ko'proq foyda qoladi."
    return card(
        item,
        verdict,
        [
            (
                "Oylik foyda o'zgarishi",
                ("+" if change >= 0 else "") + M(change),
                "",
                "good" if change >= 0 else "bad",
            ),
            ("Sotuv o'zgarishi", P(ELASTICITY * pct), f"{N(d['sold'])} → {N(vol)} porsiya", ""),
            ("Yangi FC", P(d["cost"] / new_p), f"oldin {P(d['fc'])}", ""),
        ],
        table=(
            ["Ko'rsatkich", "Hozir", "Yangi"],
            [
                ["Narx", N(d["price"]), N(new_p)],
                ["Oylik porsiya", N(d["sold"]), N(vol)],
                ["Porsiya foydasi", N(d["margin"]), N(new_p - d["cost"])],
            ],
        ),
        assumptions="Narx elastikligi −0,8 (sentyabr narx oshirishida cheklar −3% / narx +4%); boshqa taomga o'tish hisobga olinmagan.",
        source="Menyu (narx, tannarx, sotuv)",
        live=live,
        ctx=ctx,
        facts_out={"change": M(change)},
    )


@register("cost_pass_through")
def cost_pass_through(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    up = Decimal(str(p.get("pct") or 15)) / 100
    word = "go'sht"
    rec = (s.get("details") or {}).get("recipes") or {}
    rows, loss = [], D0
    for d in menu_rows(s):
        meat = sum(
            (
                _d(x.get("cost"))
                for x in rec.get(d["name"], [])
                if any(w in str(x.get("ingredient", "")).lower() for w in (word, "kotlet"))
            ),
            D0,
        )
        if meat <= 0:
            continue
        new_cost = d["cost"] + meat * up
        need = new_cost / d["fc"] if d["fc"] else d["price"]
        rounded = ((need / 1000).to_integral_value(rounding="ROUND_CEILING")) * 1000
        loss += meat * up * d["sold"]
        rows.append([d["name"], N(d["price"]), N(meat), N(rounded), f"+{N(rounded - d['price'])}"])
    avg = (
        (
            sum((_d(r[4].replace("+", "").replace(" ", "").replace("\xa0", "")) for r in rows), D0)
            / len(rows)
        )
        if rows
        else D0
    )
    verdict = (
        f"Go'sht +{int(up * 100)}% → {len(rows)} taomga ta'sir; FC'ni ushlash uchun {rows[0][0] if rows else '—'} {rows[0][4] if rows else ''} so'm."
        if rows
        else "Retseptlarda go'sht topilmadi."
    )
    live = f"Go'sht o'n besh foiz qimmatlasa, lavashlarga {say_mln(avg) if avg >= 1_000_000 else N(avg) + ' so‘m'} atrofida qo'shish kerak bo'ladi."
    return card(
        item,
        verdict,
        [
            ("Ta'sir qilgan taomlar", str(len(rows)), "", ""),
            ("Oylik zarar (narx o'zgarmasa)", M(loss), "", "bad"),
            ("O'rtacha narx o'sishi", f"+{N(avg)} so'm", "500/1000 ga yaxlitlangan", ""),
        ],
        table=(["Taom", "Hozirgi narx", "Go'sht (porsiyada)", "Yangi narx", "Farq"], rows),
        assumptions="Food cost joriy darajada ushlanadi; narx 1 000 so'mga yuqoriga yaxlitlanadi.",
        source="Texkarta (go'sht ulushi), Menyu",
        live=live,
        ctx=ctx,
        facts_out={"loss": M(loss)},
    )


@register("discount_promo_roi")
def discount_promo_roi(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    disc = Decimal(str(p.get("pct") or 20)) / 100
    be = break_even(s, last_month(s))
    m = be.cm_ratio
    need = disc / (m - disc) if m > disc else Decimal(9)
    from apps.engine import hiring as HR

    h = HR.compute(s, HR.Params())
    sat_free = (90 - h.sat_checks) / h.sat_checks if h.sat_checks else D0
    verdict = f"−{int(disc * 100)}% uchun hajm kamida +{P(need)} oshishi kerak; shanbada quvvat {'yo‘q' if sat_free < need else 'yetadi'} (bo'sh {P(sat_free)}) → faqat dushanba–payshanba qiling."
    live = f"Yigirma foiz chegirma uchun savdo kamida {uz.uz_number_words(int((need * 100).quantize(Decimal(1))))} foiz oshishi kerak — buni faqat bo'sh kunlarga qo'ying."
    return card(
        item,
        verdict,
        [
            ("Zararsizlik o'sishi", f"+{P(need)}", f"marja {P(m)}", ""),
            (
                "Kutilgan natija",
                "zarar" if need > Decimal("0.5") else "mumkin",
                "",
                "bad" if need > Decimal("0.5") else "",
            ),
            ("Quvvat", f"shanba {N(h.sat_checks)}/90", "", ""),
        ],
        assumptions="Marjinal foyda ulushi — Foyda-zarar; kannibalizatsiya (chegirmasiz ham keladiganlar) hisobga olinsa natija yomonroq.",
        source="Foyda-zarar, Smena (yuklama)",
        live=live,
        ctx=ctx,
        facts_out={"need": P(need)},
    )


@register("new_item_whatif")
def new_item_whatif(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    price = _d(p.get("amount") or 40_000)
    sim = find_dish(s, "lavash mol")
    cost = (sim["cost"] * Decimal("1.05")) if sim else price * Decimal("0.32")
    unit = price - cost
    n = ((sim["sold"] if sim else Decimal(300)) * Decimal("0.5")).quantize(Decimal(1))
    month = (unit * n * Decimal("0.75")).quantize(Decimal(1))
    verdict = f"Donar {N(price)}: porsiya foydasi {N(unit)}; oyiga ~{N(n)} porsiya → +{M(month)} (kannibalizatsiyadan keyin)."
    live = f"Donar qo'shsangiz, oyiga taxminan {say_mln(month)} qo'shimcha foyda beradi."
    return card(
        item,
        verdict,
        [
            ("Porsiya foydasi", N(unit), f"tannarx {N(cost)}", ""),
            ("Oylik foyda", M(month), "25% kannibalizatsiya", "good"),
            ("Food cost", P(cost / price), "", ""),
        ],
        assumptions=f"Tannarx — o'xshash taom ({sim['name'] if sim else '—'}) +5%; sotuv — o'xshash taomning 50%; 25% eski mijoz o'tadi (taxmin). Uskuna kerak bo'lsa → «Apparat olsam-chi?» (Q3).",
        source="Menyu, Texkarta (o'xshash taom)",
        live=live,
        ctx=ctx,
        facts_out={"month": M(month)},
    )


@register("portion_size_change")
def portion_size_change(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    d = find_dish(s, "lavash mol go'shtli")
    pur = (s.get("details") or {}).get("purchases") or {}
    lm = last_month(s)
    kg_price = _d(
        (pur.get("Mol go'shti") or {}).get("months", {}).get(lm, {}).get("price")
    ) or Decimal(110_000)
    grams = Decimal(str(p.get("grams") or 10))
    save = (grams / 1000 * kg_price * (d["sold"] if d else D0)).quantize(Decimal(1))
    new_fc = ((d["cost"] - grams / 1000 * kg_price) / d["price"]) if d else D0
    risk = (save / (d["margin"] * d["sold"])) if d and d["margin"] * d["sold"] else D0
    verdict = f"−{int(grams)} g → oyiga +{M(save)}; agar sotuv {P(risk)} dan ko'p kamaysa — zarar."
    live = f"O'n gramm kamaytirish oyiga {say_mln(save) if save >= 1_000_000 else N(save) + ' so‘m'} beradi, lekin mijoz sezsa — zarar."
    return card(
        item,
        verdict,
        [
            (
                "Oylik tejov",
                M(save),
                f"{d['name'] if d else ''}, {N(d['sold'] if d else 0)} porsiya",
                "good",
            ),
            ("Yangi FC", P(new_fc), f"oldin {P(d['fc'] if d else 0)}", ""),
            ("Xavf chegarasi", f"sotuv −{P(risk)}", "undan ko'p kamaysa — zarar", "bad"),
        ],
        assumptions=f"Mol go'shti {N(kg_price)} so'm/kg (Kirim, {lm}).",
        source="Texkarta, Kirim (go'sht narxi), Menyu (sotuv)",
        live=live,
        ctx=ctx,
        facts_out={"save": M(save)},
    )


@register("market_price_compare")
def market_price_compare(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    from .growth_tools import market, market_for

    f = facts(ctx)
    s = f["s"]
    rows, pos = [], []
    for d in menu_rows(s):
        items = market_for(d["name"])
        if not items:
            continue
        ps = sorted(_d(i["price"]) for i in items)
        med = ps[len(ps) // 2]
        dev = (d["price"] / med - 1) if med else D0
        pos.append((d["name"], dev))
        rows.append(
            [
                d["name"],
                N(d["price"]),
                f"{N(ps[0])}–{N(ps[-1])}",
                N(med),
                ("+" if dev >= 0 else "") + P(dev),
            ]
        )
    if not rows:
        return card(
            item,
            "Bozor narxlari bo'yicha manba topilmadi — raqobatchi narxlarini ayting.",
            [
                ("Pozitsiya", "—", "", ""),
                ("Eng qimmat taom", "—", "", ""),
                ("Manbalar soni", "0", "", ""),
            ],
            ctx=ctx,
        )
    top = max(pos, key=lambda x: x[1])
    lav = next((r for r in rows if "lavash" in r[0].lower()), rows[0])
    verdict = (
        f"{lav[0]}: siz {lav[1]}, bozor {lav[2]} (o'rtacha {lav[3]}) — {lav[4]} bozor o'rtachasiga."
    )
    live = "Lavashingiz bozor o'rtachasiga yaqin; arzon taomlarda narx oshirishga joy bor."
    return card(
        item,
        verdict,
        [
            ("Pozitsiya", lav[4], lav[0], ""),
            ("Eng qimmat taom", top[0], ("+" if top[1] >= 0 else "") + P(top[1]), ""),
            (
                "Manbalar soni",
                str(len(market().get("items", []))),
                f"internet, {market().get('fetched')}",
                "",
            ),
        ],
        table=(["Taom", "Siz", "Bozor (min–max)", "Bozor median", "Farq"], rows),
        assumptions="Raqobatchilar narxlari internetdan yig'ilgan (taxminiy; filial va aksiyaga qarab farq qiladi).",
        source="Menyu, bozor narxlari (Oqtepa Lavash, Evos, Max Way, Feed Up, KFC, Les Ailes)",
        live=live,
        ctx=ctx,
        facts_out={"lavash": lav[4]},
    )


# ===================== batch 5: staff, costs, forecast ==========================================
def _staff(s: dict[str, Any], role: str = "hamma") -> tuple[str, list[dict[str, Any]]]:
    from .policy_tools import staff_rows

    return staff_rows(s, role)


def _out_item(s: dict[str, Any], *words: str, month: str | None = None) -> Decimal:
    m = month or last_month(s)
    items = ((s.get("journals") or {}).get("outflow_items") or {}).get(m) or {}
    return sum((_d(v) for k, v in items.items() if any(w in k.lower() for w in words)), D0)


def _plv(s: dict[str, Any], key: str) -> Decimal:
    return pl_value(s, key, last_month(s))


def _hourly(s: dict[str, Any]) -> dict[tuple[int, int], Decimal]:
    cells = ((s.get("details") or {}).get("hourly") or {}).get("cells") or {}
    return {
        (int(k.split("|")[0]), int(k.split("|")[1])): (_d(v[0]) / _d(v[1]) if _d(v[1]) else D0)
        for k, v in cells.items()
    }


def _role_from(text: str, default: str = "hamma") -> str:
    from .policy_tools import role_in

    return role_in(text or "") or default


@register("salary_raise")
def salary_raise(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    from .policy_tools import salary_change_tool

    f = facts(ctx)
    s = f["s"]
    pct = _d(p.get("pct") or 10)
    role = _role_from(ctx.last_user_text or "")
    r = salary_change_tool(ctx, {"role": role, "pct": float(pct)})
    fx = r["facts"]
    rev = _plv(s, "sof tushum")
    m, rows = _staff(s, role)
    labor_new = (
        (sum((x["brutto"] + x["social"] for x in rows), D0) * (1 + pct / 100)) / rev if rev else D0
    )
    verdict = f"+{pct}% → oyiga +{fx['extra']} xarajat; sof foyda {fx['net']} → {fx['new_net']}; labor {P(labor_new)}."
    return card(
        item,
        verdict,
        [
            ("Qo'shimcha xarajat", fx["extra"], f"{len(rows)} xodim", "bad"),
            ("Yangi sof foyda", fx["new_net"], f"oldin {fx['net']}", ""),
            (
                "Labor %",
                P(labor_new),
                "maqsad ≤ 25%",
                "good" if labor_new <= Decimal("0.25") else "bad",
            ),
        ],
        actions=[
            "Ko'tarish o'rniga KPI bonus (savdo/tezlik)",
            "Kalit xodimlarga (bosh oshpaz) ustuvorlik",
            "Narx/hajm bilan qoplang",
        ],
        source=f"Ish haqi ({m}), Foyda-zarar",
        live=f"Oylikni {uz.uz_number_words(int(pct))} foiz oshirsangiz, oyiga {fx['extra']} qo'shimcha xarajat bo'ladi.",
        ctx=ctx,
        facts_out=fx,
    )


@register("staff_cut")
def staff_cut(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    role = _role_from(ctx.last_user_text or "", "kassir")
    m, rows = _staff(s, role)
    if not rows:
        m, rows = _staff(s, "hamma")
    x = min(rows, key=lambda r: r["total"])
    from apps.engine import hiring as HR

    meals = HR.compute(s, HR.Params()).meals
    save = x["total"] + meals
    same = [r for r in _staff(s, "hamma")[1] if r["position"] == x["position"]]
    a = 100 / max(1, len(same)) if same else 100
    b = 100 / max(1, len(same) - 1) if len(same) > 1 else 200
    risk = "yuqori" if len(same) <= 1 else ("o'rta" if len(same) == 2 else "past")
    load = (
        f"har biriga yuklama +{int(b - a)}%"
        if len(same) > 1
        else "bu lavozimda boshqa odam yo'q — vazifani boshqalar bo'lishadi"
    )
    who = x["position"] if x["name"] == x["position"] else f"{x['position']} ({x['name']})"
    verdict = f"{who}: oyiga {M(save)} tejov; {load}; xavf {risk}."
    return card(
        item,
        verdict,
        [
            ("Oylik tejov", M(save), "brutto + soliq + ovqat", "good"),
            (
                "Yangi yuklama",
                (
                    f"{len(same) - 1} kishi {len(same)} kishilik ishni"
                    if len(same) > 1
                    else "o'rnini hech kim bosmaydi"
                ),
                x["position"],
                "bad" if len(same) <= 2 else "",
            ),
            ("Xavf", risk, "xizmat sekinlashishi", "bad" if risk != "past" else ""),
        ],
        actions=[
            "Avval smena jadvalini qayta tuzib ko'ring",
            "Pik soatlarda yuklamani o'lchang (Soatlik savdo)",
            "Bo'shatish o'rniga yarim stavka",
        ],
        source=f"Ish haqi ({m}), Soatlik savdo",
        live=f"Bitta {x['position'].lower()}ni bo'shatsangiz oyiga {say_mln(save)} tejaysiz, lekin xizmat sekinlashishi mumkin.",
        ctx=ctx,
        facts_out={"save": M(save)},
    )


@register("formalize_staff_tax")
def formalize_staff_tax(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    m, rows = _staff(s, "hamma")
    inf = [r for r in rows if not r["official"]]
    br = sum((r["brutto"] for r in inf), D0)
    social = (br * Decimal("0.12")).quantize(Decimal(1))
    gross_up = (br / Decimal("0.88") - br).quantize(Decimal(1))
    net = _plv(s, "sof foyda")
    verdict = f"{len(inf)} xodim: oyiga +{M(social)} (ijtimoiy), netto saqlansa yana +{M(gross_up)}. Yillik {M((social + gross_up) * 12)}."
    return card(
        item,
        verdict,
        [
            (
                "Oylik qo'shimcha",
                M(social + gross_up),
                "ijtimoiy 12% + JShDS 12% (netto saqlansa)",
                "bad",
            ),
            ("Yillik", M((social + gross_up) * 12), "", ""),
            (
                "Foydaga ta'sir",
                P((social + gross_up) / net) if net else "—",
                f"sof foyda {M(net)}",
                "",
            ),
        ],
        table=(
            ["Xodim", "Lavozim", "Brutto"],
            [[r["name"], r["position"], N(r["brutto"])] for r in inf],
        ),
        assumptions="Ijtimoiy soliq 12% (ish beruvchi), JShDS 12% (xodimdan; netto saqlash uchun brutto oshiriladi).",
        source=f"Ish haqi ({m}, 'Rasmiy' ustuni)",
        live=f"Norasmiy xodimlarni rasmiylashtirish oyiga {say_mln(social + gross_up)} qo'shimcha xarajat.",
        ctx=ctx,
        facts_out={"monthly": M(social + gross_up)},
    )


@register("extend_hours_24h")
def extend_hours_24h(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    hr = _hourly(s)
    last_h = max((h for _, h in hr), default=22)
    late = sum((v for (w, h), v in hr.items() if h == last_h), D0) / 7 if hr else Decimal(3)
    avg = _plv(s, "o'rtacha chek so'm") or Decimal(80_000)
    night_checks = late * Decimal("0.35") * 8
    rev = (night_checks * avg * 30).quantize(Decimal(1))
    be = break_even(s, last_month(s))
    cost = Decimal(2) * Decimal(3_500_000) + Decimal(1_500_000) + Decimal(1_000_000)
    res = (rev * be.cm_ratio - cost).quantize(Decimal(1))
    verdict = (
        f"Tungi soatlar ~{M(rev)} tushum, {M(cost)} xarajat → {'+' if res >= 0 else ''}{M(res)}/oy."
    )
    return card(
        item,
        verdict,
        [
            ("Tungi tushum", M(rev), f"~{N(night_checks)} chek/tun", ""),
            ("Tungi xarajat", M(cost), "2 xodim + energiya + xavfsizlik", ""),
            ("Natija", ("+" if res >= 0 else "") + M(res), "oyiga", "good" if res > 0 else "bad"),
        ],
        assumptions=f"Tungi sur'at = oxirgi soat ({last_h}:00) sur'atining 35% (taxmin); 2 tungi xodim 3,5 mln dan.",
        source="Soatlik savdo, Ish haqi, Energiya",
        live=f"Yigirma to'rt soat ishlash oyiga {'foyda' if res > 0 else 'zarar'} beradi — {say_mln(res)}.",
        ctx=ctx,
        facts_out={"result": M(res)},
    )


@register("close_one_day")
def close_one_day(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    wz = {int(k): _d(v) for k, v in ((s.get("journals") or {}).get("weekday_z") or {}).items()}
    day = min(wz, key=lambda k: wz[k]) if wz else 0
    be = break_even(s, last_month(s))
    lost = (wz.get(day, D0) * Decimal("4.33") * be.cm_ratio * Decimal("0.7")).quantize(Decimal(1))
    save = (Decimal("4.33") * (Decimal(180_000) + Decimal(150_000))).quantize(Decimal(1))
    res = save - lost
    verdict = f"{DAYS_UZ[day].capitalize()} yopilsa: −{M(lost)} yalpi foyda, +{M(save)} tejov → {'+' if res >= 0 else ''}{M(res)}/oy."
    return card(
        item,
        verdict,
        [
            ("Yo'qotilgan foyda", M(lost), "30% boshqa kunga o'tadi", "bad"),
            ("Tejov", M(save), "energiya + kunbay", ""),
            ("Natija", ("+" if res >= 0 else "") + M(res), "oyiga", "good" if res > 0 else "bad"),
        ],
        table=(
            ["Hafta kuni", "O'rtacha savdo"],
            [[DAYS_UZ[k].capitalize(), N(v)] for k, v in sorted(wz.items())],
        ),
        assumptions="Yopilgan kun savdosining 30% boshqa kunlarga o'tadi; tejov — energiya ~180 000 + kunbay ~150 000 so'm/kun (taxmin).",
        source="Smena (hafta kunlari), Foyda-zarar",
        live=f"{DAYS_UZ[day].capitalize()} yopish oyiga {'foyda' if res > 0 else 'zarar'} — {say_mln(res)}.",
        ctx=ctx,
        facts_out={"result": M(res)},
    )


@register("staff_turnover_cost")
def staff_turnover_cost(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    m, rows = _staff(s, "oshpaz")
    chef = max(rows, key=lambda r: r["oklad"]) if rows else None
    sal = chef["total"] if chef else Decimal(5_000_000)
    hire = (sal * Decimal("1.5")).quantize(Decimal(1))
    rev = _plv(s, "sof tushum")
    be = break_even(s, last_month(s))
    lost = (rev * Decimal("0.05") * be.cm_ratio * 2).quantize(Decimal(1))
    verdict = f"{chef['name'] if chef else 'Bosh oshpaz'} ketsa ~{M(hire + lost)} (yollash {M(hire)} + yo'qotilgan savdo {M(lost)})."
    return card(
        item,
        verdict,
        [
            ("Jami zarar", M(hire + lost), "", "bad"),
            ("Yollash xarajati", M(hire), "1,5 oylik oylik", ""),
            ("Tiklanish muddati", "~2 oy", "savdo −5%", ""),
        ],
        actions=[
            "Retseptlarni (Texkarta) to'liq hujjatlashtiring",
            "Ikkinchi oshpazni o'rinbosar qilib tayyorlang",
            "Bosh oshpazga uzoq muddatli bonus (6 oyda bir)",
        ],
        source=f"Ish haqi ({m}), Foyda-zarar",
        live=f"Bosh oshpaz ketsa taxminan {say_mln(hire + lost)} zarar — o'rinbosar tayyorlang.",
        ctx=ctx,
        facts_out={"total": M(hire + lost)},
    )


@register("payroll_split")
def payroll_split(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    pay = next((o for o in f["obligations"] if o.category == "payroll"), None)
    if pay is None:
        return card(item, "Oylik to'lovi kalendarda topilmadi.", [("—", "—", "", "")] * 3, ctx=ctx)
    pct = Decimal(str(p.get("pct") or 40)) / 100
    adv = (_d(pay.amount) * pct).quantize(Decimal(1))
    d20 = (
        date(pay.date.year, pay.date.month, 20)
        if pay.date.day > 20
        else (pay.date.replace(day=1) - timedelta(days=1)).replace(day=20)
    )
    new_close = {d: f["close"][d] - (adv if d20 <= d < pay.date else D0) for d in f["days"]}
    a, b = f["min_balance"], min(new_close.values())
    verdict = (
        f"Avans {int(pct * 100)}% 20-sanada: eng tang kun {M(a)} → {M(b)}; jami summa o'zgarmaydi."
    )
    return card(
        item,
        verdict,
        [
            ("Eng tang kun (oldin/keyin)", f"{M(a)} → {M(b)}", "", "good" if b >= a else ""),
            ("Avans summasi", M(adv), "20-sana", ""),
            ("Xodimlar uchun", "oyda 2 marta pul", "sodiqlik oshadi", "good"),
        ],
        source="Ish haqi, kunlik prognoz",
        live="Avans berish kassangizni tekislaydi, jami summa o'zgarmaydi.",
        ctx=ctx,
        facts_out={"advance": M(adv)},
    )


@register("rent_increase")
def rent_increase(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    pct = Decimal(str(p.get("pct") or 20)) / 100
    rent = _plv(s, "ijara")
    rev = _plv(s, "sof tushum")
    be = break_even(s, last_month(s))
    extra = (rent * pct).quantize(Decimal(1))
    comp = (extra / be.cm_ratio).quantize(Decimal(1)) if be.cm_ratio else D0
    verdict = f"+{int(pct * 100)}% → oyiga −{M(extra)}; ijara {P(rent / rev)} → {P(rent * (1 + pct) / rev)} tushum. Qoplash: tushum +{M(comp)}/oy yoki muzokara."
    return card(
        item,
        verdict,
        [
            ("Oylik ta'sir", "−" + M(extra), "", "bad"),
            (
                "Ijara % tushum",
                P(rent * (1 + pct) / rev),
                "maqsad ≤ 10%",
                "good" if rent * (1 + pct) / rev <= Decimal("0.1") else "bad",
            ),
            ("Kerakli kompensatsiya", M(comp), "qo'shimcha tushum/oy", ""),
        ],
        actions=[
            "Muzokara: uzoq muddatli shartnoma evaziga oshishni 10% gacha",
            "Kompensatsiya: qo'shimcha sotuv / lanch-set",
            "Muqobil joy narxlarini o'rganing (web)",
        ],
        source="Hisoblash (Ijara), Foyda-zarar",
        live=f"Ijara yigirma foiz oshsa oyiga {say_mln(extra)} kam foyda; uzoq muddatli shartnoma bilan muzokara qiling.",
        ctx=ctx,
        facts_out={"extra": M(extra)},
    )


@register("packaging_cost")
def packaging_cost(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    q = _out_item(s, "qadoq")
    ch = (((s.get("details") or {}).get("channels") or {}).get("months") or {}).get(lm, {})
    nonhall = sum((_d(v["revenue"]) for k, v in ch.items() if "zal" not in k.lower()), D0)
    rows_n = sum((int(v.get("rows", 0)) for k, v in ch.items() if "zal" not in k.lower()), 0)
    pct = q / nonhall if nonhall else D0
    per = q / rows_n if rows_n else D0
    prev = _out_item(
        s, "qadoq", month=(date.fromisoformat(lm) - timedelta(days=1)).replace(day=1).isoformat()
    )
    verdict = f"Qadoq {P(pct)} (zaldan tashqari) — {'normal' if pct <= Decimal('0.03') else 'yuqori'}; buyurtmaga ~{N(per)} so'm."
    return card(
        item,
        verdict,
        [
            ("Qadoq %", P(pct), "norma 2–3%", "good" if pct <= Decimal("0.03") else "bad"),
            ("Buyurtmaga", f"{N(per)} so'm", "taxmin", ""),
            ("Trend", f"{M(prev)} → {M(q)}", "o'tgan oy → oxirgi", ""),
        ],
        source=f"Kassa (Qadoqlash materiallari, {lm}), Sotuv kanallari",
        live=f"Qadoq xarajatingiz {'normal' if pct <= Decimal('0.03') else 'yuqori'} — zaldan tashqari tushumning {P(pct)}.",
        ctx=ctx,
        facts_out={"pct": P(pct)},
    )


@register("payment_fees")
def payment_fees(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    fee = _out_item(s, "komissiya", "bank")
    card_rev = _plv(s, "sof tushum") * Decimal("0.6")
    pct = fee / card_rev if card_rev else D0
    save = (card_rev * Decimal("0.003") * 12).quantize(Decimal(1))
    verdict = (
        f"Komissiya {M(fee)}/oy ({P(pct)}). Tarifni 0,3 p.p. ga tushirish {M(save)}/yil tejaydi."
    )
    return card(
        item,
        verdict,
        [
            ("Oylik komissiya", M(fee), "", ""),
            ("% karta tushumi", P(pct), "karta ~60% (taxmin)", ""),
            ("Tejov imkoni", M(save), "yiliga", "good"),
        ],
        actions=[
            "Bankingizdan aylanma hajmi bo'yicha tarif so'rang",
            "2–3 bank takliflarini solishtiring",
            "Naqd/QR to'lovni rag'batlantiring",
        ],
        source="Kassa (Bank komissiyasi), Foyda-zarar",
        live=f"Bank komissiyasi oyiga {say_mln(fee)}; tarifni tushirsangiz yiliga {say_mln(save)} tejaysiz.",
        ctx=ctx,
        facts_out={"fee": M(fee)},
    )


@register("supplier_switch")
def supplier_switch(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    pur = (s.get("details") or {}).get("purchases") or {}
    name, d = max(
        pur.items(), key=lambda kv: _d((kv[1].get("months") or {}).get(lm, {}).get("amount"))
    )
    mo = (d.get("months") or {}).get(lm, {})
    price, qty = _d(mo.get("price")), _d(mo.get("qty"))
    new = (price * Decimal("0.95")).quantize(Decimal(1))
    save = ((price - new) * qty).quantize(Decimal(1))
    verdict = f"{name}: {N(price)} → {N(new)} so'm/{d.get('unit', 'kg')} → oyiga {M(save)} tejov."
    return card(
        item,
        verdict,
        [
            ("Oylik tejov", M(save), "5% arzonroq taklif (taxmin)", "good"),
            ("Yillik", M(save * 12), "", ""),
            ("Xavf", "sifat / ishonchlilik", "2 haftalik sinov", ""),
        ],
        actions=[
            "2 ta muqobil ta'minotchidan narx so'rang",
            "2 hafta parallel sinov (sifat, vaqtida yetkazish)",
            "Eski ta'minotchi bilan narxni qayta kelishing",
        ],
        source=f"Kirim ({name}, {lm})",
        live=f"{name}ni arzonroq olsangiz oyiga {say_mln(save) if save >= 1_000_000 else N(save) + ' so‘m'} tejaysiz.",
        ctx=ctx,
        facts_out={"save": M(save)},
    )


@register("staff_meals_cost")
def staff_meals_cost(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    meals = _plv(s, "xodimlar ovqati")
    m, rows = _staff(s, "hamma")
    per = meals / len(rows) if rows else D0
    rev = _plv(s, "sof tushum")
    from apps.engine import hiring as HR

    norm = HR.compute(s, HR.Params()).meals * Decimal("2.2")
    verdict = f"Oyiga {M(meals)}, xodim boshiga {M(per)}; normaga (kuniga 1 porsiya ~{M(norm)}) nisbatan {'normal' if per <= norm * Decimal('1.15') else 'yuqori'}."
    return card(
        item,
        verdict,
        [
            ("Oylik", M(meals), "", ""),
            (
                "Xodim boshiga",
                M(per),
                f"{len(rows)} xodim",
                "good" if per <= norm * Decimal("1.15") else "bad",
            ),
            ("% tushum", P(meals / rev) if rev else "—", "", ""),
        ],
        source=f"Foyda-zarar (Xodimlar ovqati), Ish haqi ({m})",
        live=f"Xodimlar ovqati oyiga {say_mln(meals)} — normal darajada.",
        ctx=ctx,
        facts_out={"meals": M(meals)},
    )


@register("supplier_volume_discount")
def supplier_volume_discount(
    ctx: ToolContext, item: CatalogItem, p: dict[str, Any]
) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    tot: dict[str, Decimal] = {}
    for _n, d in ((s.get("details") or {}).get("purchases") or {}).items():
        sup = d.get("suppliers") or {}
        if isinstance(sup, dict):
            for k, v in sup.items():
                tot[k] = tot.get(k, D0) + _d(v if not isinstance(v, dict) else v.get("amount"))
    if not tot:
        return card(
            item,
            "Ta'minotchilar bo'yicha xaridlar topilmadi (Kirim varag'ida 'Yetkazib beruvchi' ustuni).",
            [("—", "—", "", "")] * 3,
            ctx=ctx,
        )
    big, v = max(tot.items(), key=lambda kv: kv[1])
    lm = last_month(s)
    year = v / max(1, int(lm[5:7])) * 12
    save = (year * Decimal("0.03")).quantize(Decimal(1))
    verdict = f"{big}: yillik {M(year)} — 3% chegirma {M(save)}/yil."
    return card(
        item,
        verdict,
        [
            ("Eng katta yetkazib beruvchi", big, "", ""),
            ("Yillik hajm", M(year), "", ""),
            ("Tejov (3%)", M(save), "yiliga", "good"),
        ],
        table=(
            ["Ta'minotchi", "Yil boshidan"],
            [[k, N(x)] for k, x in sorted(tot.items(), key=lambda kv: -kv[1])[:8]],
        ),
        source="Kirim (yetkazib beruvchilar)",
        live=f"Eng katta ta'minotchidan uch foiz chegirma yiliga {say_mln(save)} beradi.",
        ctx=ctx,
        facts_out={"save": M(save)},
    )


@register("year_end_forecast")
def year_end_forecast(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    pl = (s.get("reports") or {}).get("pl") or {}
    lm = last_month(s)
    yr = lm[:4]
    rev_fact = sum(
        (_d(v) for k, v in (pl.get("sof tushum") or {}).items() if k.startswith(yr) and k <= lm), D0
    )
    net_fact = sum(
        (_d(v) for k, v in (pl.get("sof foyda") or {}).items() if k.startswith(yr) and k <= lm), D0
    )
    seas = {
        int(k): _d(v) for k, v in ((s.get("details") or {}).get("seasonality") or {}).items()
    } or {m: Decimal(1) for m in range(1, 13)}
    be = break_even(s, lm)
    base = be.revenue / seas.get(int(lm[5:7]), Decimal(1))
    rest = [m for m in range(int(lm[5:7]) + 1, 13)]
    rev_rest = sum((base * seas.get(m, Decimal(1)) for m in rest), D0)
    net_rest = sum((base * seas.get(m, Decimal(1)) * be.cm_ratio - be.fixed for m in rest), D0)
    dec = base * seas.get(12, Decimal(1)) * be.cm_ratio - be.fixed
    tr, tn = rev_fact + rev_rest, net_fact + net_rest
    verdict = f"{yr}: tushum ~{M(tr)}, sof foyda ~{M(tn)} ({M(tn * Decimal('0.9'))}–{M(tn * Decimal('1.1'))})."
    return card(
        item,
        verdict,
        [
            ("Yillik tushum", M(tr), f"fakt {M(rev_fact)} + prognoz", ""),
            ("Yillik sof foyda", M(tn), "±10%", "good" if tn > 0 else "bad"),
            (
                "Dekabr prognozi",
                M(dec),
                f"mavsum {str(seas.get(12, Decimal(1))).replace('.', ',')}",
                "",
            ),
        ],
        source="Foyda-zarar (yil boshidan), Fin reja (mavsum)",
        live=f"Yil oxirigacha sof foyda taxminan {say_mln(tn)} bo'ladi.",
        ctx=ctx,
        facts_out={"net": M(tn)},
    )


@register("target_profit_reverse")
def target_profit_reverse(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    be = break_even(s, last_month(s))
    target = _d(p.get("amount") or 30_000_000)
    rev = (be.fixed + target) / be.cm_ratio if be.cm_ratio else D0
    c = (rev / be.avg_check / be.days).quantize(Decimal(1)) if be.avg_check and be.days else D0
    h = be.checks_per_day.quantize(Decimal(1))
    from apps.engine import hiring as HR

    hh = HR.compute(s, HR.Params())
    cap_ok = c <= Decimal(90) * Decimal("0.95") + (hh.sat_checks - hh.weekday_checks) / 7
    verdict = f"{M(target)} foyda uchun kuniga {N(c)} chek (hozir {N(h)}, +{N(c - h)}). Quvvat: {'yetadi' if cap_ok else 'yo‘q'}."
    return card(
        item,
        verdict,
        [
            ("Kerakli cheklar/kun", N(c), f"tushum {M(rev)}/oy", ""),
            ("Hozir", N(h), "", ""),
            ("Farq", f"+{N(c - h)}", "chek/kun", ""),
        ],
        source="Foyda-zarar, Smena",
        live=f"{say_mln(target).capitalize()} foyda uchun kuniga {uz.uz_number_words(int(c))} ta chek kerak.",
        ctx=ctx,
        facts_out={"checks": N(c)},
    )


@register("holiday_stock_plan")
def holiday_stock_plan(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    sd = {x[0]: _d(x[1]) for x in ((s.get("details") or {}).get("smena_days") or [])}
    base = (sum(sd.values(), D0) / len(sd)) if sd else Decimal(60)
    hol = (
        sd.get(f"{f['today'].year}-03-21")
        or sd.get(f"{f['today'].year}-01-01")
        or base * Decimal("1.3")
    )
    k = (hol / base).quantize(Decimal("0.1")) if base else Decimal("1.3")
    avg = _plv(s, "o'rtacha chek so'm") or Decimal(80_000)
    rev = (base * k * avg).quantize(Decimal(1))
    verdict = f"Bayram: savdo ~{str(k).replace('.', ',')}x (o'tgan bayram), tushum ~{M(rev)}/kun. Xarid: lavash, go'sht, tovuq +{P(k - 1)}; +2 kunbay."
    return card(
        item,
        verdict,
        [
            ("Kutilgan savdo", f"{str(k).replace('.', ',')}x", f"{N(base * k)} chek/kun", ""),
            ("Qo'shimcha xarid", f"+{P(k - 1)}", "asosiy masalliqlar", ""),
            ("Qo'shimcha xodim", "+2 kunbay", "", ""),
        ],
        source="Smena (bayram kunlari), Texkarta",
        live=f"Bayramda savdo taxminan {str(k).replace('.', ',')} barobar oshadi — masalliqni oldindan oling.",
        ctx=ctx,
        facts_out={"k": str(k)},
    )


@register("one_year_projection")
def one_year_projection(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    from apps.engine import hiring as HR

    f = facts(ctx)
    s = f["s"]
    be = break_even(s, last_month(s))
    h = HR.compute(s, HR.Params())
    g = h.hall_growth
    rev12 = be.revenue * (1 + g) ** 12
    prof12 = rev12 * be.cm_ratio - be.fixed
    cash12 = f["cash"] + sum(
        (be.revenue * (1 + g) ** i * be.cm_ratio - be.fixed for i in range(1, 13)), D0
    ) * Decimal("0.7")
    verdict = f"1 yilda: tushum ~{M(rev12)}/oy, foyda ~{M(prof12)}/oy, kassa ~{M(cash12)}. Quvvat ~{h.hire_month or '—'}da to'ladi."
    return card(
        item,
        verdict,
        [
            ("Tushum (12 oy keyin)", M(rev12), f"o'sish {P(g)}/oy", ""),
            ("Foyda", M(prof12), "oyiga", "good"),
            ("Quvvat sanasi", h.hire_month or "—", "shanba 95%", ""),
        ],
        source="Smena (trend), Foyda-zarar, Fin reja",
        live=f"Shu sur'atda bir yildan keyin oyiga {say_mln(prof12)} foyda; quvvat {h.hire_month or ''}da to'ladi.",
        ctx=ctx,
        facts_out={"profit12": M(prof12), "capacity": h.hire_month},
    )


@register("best_month_big_spend")
def best_month_big_spend(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    amt = _d(p.get("amount") or 30_000_000)
    best = None
    risky = []
    for d in f["days"][:90]:
        after = min(f["close"][x] for x in f["days"] if x >= d) - amt
        if after >= f["buffer"] and best is None:
            best = (d, after)
        if after < f["buffer"]:
            risky.append(d.strftime("%m.%Y"))
    if best is None:
        verdict = (
            f"{M(amt)} uchun keyingi 90 kunda xavfsiz kun yo'q — bo'lib to'lash yoki jamg'arma."
        )
        return card(
            item,
            verdict,
            [
                ("Eng yaxshi oy", "—", "", "bad"),
                ("O'sha oyda min kassa", "—", "", ""),
                ("Xavfli oylar", ", ".join(sorted(set(risky))[:3]), "", "bad"),
            ],
            ctx=ctx,
        )
    d, after = best
    verdict = f"{M(amt)} uchun eng yaxshi vaqt — {Dt(d)} (agregator to'lovidan keyin): keyin eng past kassa {M(after)}."
    return card(
        item,
        verdict,
        [
            ("Eng yaxshi oy", Dt(d), "", "good"),
            ("O'sha oyda min kassa", M(after), f"chegara {M(f['buffer'])}", ""),
            ("Xavfli oylar", ", ".join(sorted(set(risky))[:3]) or "yo'q", "", ""),
        ],
        chart={
            "title": "Kassa va xarid ta'siri",
            **cash_chart(f, 90, {x: amt for x in f["days"] if x >= d}),
        },
        source="Kunlik prognoz",
        live=f"Katta xaridni {d.day}-{uz.MONTHS[d.month - 1]}dan keyin qiling.",
        ctx=ctx,
        facts_out={"best": d.isoformat()},
    )


@register("daily_target")
def daily_target(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    wz = {int(k): _d(v) for k, v in ((s.get("journals") or {}).get("weekday_z") or {}).items()}
    tot = sum(wz.values(), D0)
    month_target = _plv(s, "sof tushum") * Decimal("1.10")
    days = []
    for i in range(7):
        d = f["today"] + timedelta(days=i)
        share = wz.get(d.weekday(), D0) / tot if tot else Decimal(1) / 7
        days.append((d, (month_target / Decimal("4.33") * share).quantize(Decimal(1))))
    t0 = days[0][1]
    verdict = f"Bugun ({DAYS_UZ[f['today'].weekday()]}) maqsad {M(t0)}; oylik maqsad {M(month_target)} (oxirgi oy +10%)."
    return card(
        item,
        verdict,
        [
            ("Bugungi maqsad", M(t0), DAYS_UZ[f["today"].weekday()], ""),
            ("Oylik maqsad", M(month_target), "+10%", ""),
            ("Bajarilish", "kun oxirida", "Smena bo'yicha", ""),
        ],
        table=(
            ["Kun", "Maqsad"],
            [[f"{DAYS_UZ[d.weekday()].capitalize()} {d.day}", N(v)] for d, v in days],
        ),
        source="Smena (hafta kunlari), Foyda-zarar",
        live=f"Bugungi maqsad {say_mln(t0)}.",
        ctx=ctx,
        facts_out={"today": M(t0)},
    )


@register("late_hours_profit")
def late_hours_profit(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    hr = _hourly(s)
    avg = _plv(s, "o'rtacha chek so'm") or Decimal(80_000)
    be = break_even(s, last_month(s))
    late = {w: sum((v for (ww, h), v in hr.items() if ww == w and h >= 22), D0) for w in range(7)}
    rev = sum(late.values(), D0) * Decimal("4.33") * avg
    cost = Decimal(2) * Decimal("4.33") * 7 * Decimal(60_000) + Decimal("4.33") * 7 * Decimal(
        25_000
    )
    prof = (rev * be.cm_ratio - cost).quantize(Decimal(1))
    bad = [
        DAYS_UZ[w]
        for w, v in late.items()
        if v * avg * be.cm_ratio < 2 * Decimal(60_000) + Decimal(25_000)
    ]
    verdict = f"22–24: oyiga {M(rev)} tushum, {'+' if prof >= 0 else ''}{M(prof)} foyda; {(', '.join(bad) + 'da zarar') if bad else 'zarar kuni yo‘q'}."
    return card(
        item,
        verdict,
        [
            (
                "Kechki foyda",
                ("+" if prof >= 0 else "") + M(prof),
                "oyiga",
                "good" if prof > 0 else "bad",
            ),
            ("Zarar kunlari", str(len(bad)), ", ".join(bad[:3]), ""),
            ("Energiya", M(Decimal("4.33") * 7 * Decimal(25_000)), "oyiga", ""),
        ],
        table=(
            ["Kun", "22–24 cheklar"],
            [[DAYS_UZ[w].capitalize(), str(v.quantize(Decimal("0.1")))] for w, v in late.items()],
        ),
        source="Soatlik savdo, Foyda-zarar",
        live=f"Kechki ikki soat oyiga {say_mln(prof)} {'foyda' if prof > 0 else 'zarar'}; {', '.join(bad[:2])} kunlari yopish mumkin.",
        ctx=ctx,
        facts_out={"profit": M(prof)},
    )


# ===================== batch 6: control, owner ===================================================
def _smena(s: dict[str, Any]) -> list[list[Any]]:
    return [r for r in ((s.get("details") or {}).get("smena_days") or []) if len(r) >= 3]


def _bar(
    title: str, labels: list[str], vals: list[Decimal], unit: str = "mln so'm", div: int = 1_000_000
) -> dict[str, Any]:
    return {
        "type": "bar",
        "title": title,
        "unit": unit,
        "x_labels": labels,
        "series": [
            {
                "name": title,
                "color": "#14B8A6",
                "data": [float((v / div).quantize(Decimal("0.01"))) for v in vals],
            }
        ],
    }


def _cash_rows(s: dict[str, Any]) -> list[list[Any]]:
    return [r for r in ((s.get("details") or {}).get("smena_cash") or []) if len(r) >= 6]


def _prev_month(m: str) -> str:
    return (date.fromisoformat(m) - timedelta(days=1)).replace(day=1).isoformat()


def _mname(m: str) -> str:
    return uz.MONTHS[int(m[5:7]) - 1].capitalize()


@register("cash_discrepancy")
def cash_discrepancy(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    rows = _cash_rows(s)[-30:]
    filled = [(r[0], _d(r[2]), _d(r[3])) for r in rows if r[3] != ""]
    pos_total = sum((_d(r[2]) for r in rows), D0)
    per = (
        f"{Dt(date.fromisoformat(rows[0][0]))} – {Dt(date.fromisoformat(rows[-1][0]))}"
        if rows
        else "oxirgi 30 kun"
    )
    if not filled:
        verdict = f"{per}: 'Naqd kassaga (haqiqiy)' ustuni bo'sh — farqni tekshirib bo'lmaydi; POS bo'yicha naqd {M(pos_total)}."
        return card(
            item,
            verdict,
            [
                ("Jami farq", "—", "haqiqiy naqd yozilmagan", ""),
                ("Farqli kunlar", "—", f"{len(rows)} smena", ""),
                ("POS naqd", M(pos_total), "30 kun", ""),
            ],
            actions=[
                "Har kuni haqiqiy naqdni yozing",
                "Kassir almashinuvida sanang",
                "Farq > 50 000 so'm bo'lsa — tekshiruv",
            ],
            source="Smena (Naqd POS, Naqd kassaga)",
            live="Haqiqiy naqd ustuni to'ldirilmagan — har kuni yozib boring, shunda farqni ko'raman.",
            ctx=ctx,
            facts_out={"filled": 0},
        )
    diffs = [(d, pos, till, till - pos) for d, pos, till in filled]
    tot = sum((x[3] for x in diffs), D0)
    bad = [x for x in diffs if abs(x[3]) >= 1000]
    big = min(diffs, key=lambda x: x[3])
    state = "jiddiy farq yo'q" if abs(tot) < 50_000 and abs(big[3]) < 50_000 else "tekshiruv kerak"
    verdict = f"{per}: naqd farq {N(tot)} so'm ({len(bad)} kun). {state.capitalize()}."
    return card(
        item,
        verdict,
        [
            (
                "Jami farq",
                f"{N(tot)} so'm",
                f"{len(filled)} kun yozilgan",
                "good" if abs(tot) < 50_000 else "bad",
            ),
            ("Farqli kunlar", str(len(bad)), "|farq| ≥ 1 000", ""),
            (
                "Eng katta",
                f"{N(big[3])} so'm",
                Dt(date.fromisoformat(big[0])),
                "bad" if abs(big[3]) >= 50_000 else "",
            ),
        ],
        chart=_bar("Kunlik naqd farq", [x[0][5:] for x in diffs], [x[3] for x in diffs], "so'm", 1),
        table=(
            ["Sana", "POS", "Haqiqiy", "Farq"],
            [
                [Dt(date.fromisoformat(x[0])), N(x[1]), N(x[2]), N(x[3])]
                for x in sorted(diffs, key=lambda x: x[3])[:10]
            ],
        ),
        actions=[
            "Har kuni haqiqiy naqdni yozing",
            "Kassir almashinuvida sanang",
            "Farq > 50 000 so'm — tekshiruv",
        ],
        source="Smena (Naqd POS vs Naqd kassaga)",
        live=f"Naqd farq jami {say_mln(tot) if abs(tot) >= 1_000_000 else N(tot) + ' so‘m'} — {state}.",
        ctx=ctx,
        facts_out={"total": N(tot), "days": len(bad)},
    )


@register("anomaly_days")
def anomaly_days(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    rows = _smena(s)
    recs = [(date.fromisoformat(r[0]), _d(r[1]), r[2]) for r in rows]
    avg = _plv(s, "o'rtacha chek so'm") or Decimal(80_000)
    out = []
    last = recs[-60:]
    for d, c, note in last:
        same = [
            x[1]
            for x in recs
            if x[0].weekday() == d.weekday() and timedelta(0) < d - x[0] <= timedelta(days=63)
        ]
        if len(same) < 4:
            continue
        mu = sum(same, D0) / len(same)
        sd = (sum(((x - mu) ** 2 for x in same), D0) / len(same)).sqrt()
        if sd and (c - mu) / sd < -2:
            out.append(
                (
                    d,
                    mu,
                    c,
                    note or ("bayram oldi" if d.month == 12 and d.day >= 30 else "sababi noma'lum"),
                )
            )
    lost = sum(((mu - c) * avg for _, mu, c, _ in out), D0)
    if not out:
        verdict = "Oxirgi 60 kunda g'ayrioddiy past kun yo'q (z < −2 mezoni)."
        return card(
            item,
            verdict,
            [
                ("G'ayrioddiy kunlar", "0", "60 kun", "good"),
                ("Eng katta og'ish", "—", "", ""),
                ("Yo'qotilgan tushum", "0", "", ""),
            ],
            source="Smena (kunlik cheklar, izoh)",
            live="Oxirgi ikki oyda savdo g'ayrioddiy past bo'lgan kun yo'q.",
            ctx=ctx,
            facts_out={"n": 0},
        )
    w = min(out, key=lambda x: x[2] / x[1])
    pct = w[2] / w[1] - 1
    verdict = f"{len(out)} ta g'ayrioddiy kun: {Dt(w[0])} ({P(pct)}) — {w[3]}."
    return card(
        item,
        verdict,
        [
            ("G'ayrioddiy kunlar", str(len(out)), "oxirgi 60 kun", "bad"),
            ("Eng katta og'ish", P(pct), Dt(w[0]), "bad"),
            ("Yo'qotilgan tushum", M(lost), "taxmin", ""),
        ],
        table=(
            ["Sana", "Kutilgan", "Fakt", "Sabab"],
            [[Dt(d), N(mu), N(c), note] for d, mu, c, note in out],
        ),
        actions=[
            "Sababi noma'lum kunlarni tekshiring",
            "Izoh ustuniga sababni yozib boring",
            "Takrorlansa — chora (aksiya, xodim)",
        ],
        assumptions="Kutilgan = so'nggi 9 haftadagi shu hafta kunining o'rtachasi; g'ayrioddiy = z < −2.",
        source="Smena (kunlik cheklar, izoh)",
        live=f"Oxirgi ikki oyda {uz.uz_number_words(len(out))} kun savdo kutilganidan past bo'ldi.",
        ctx=ctx,
        facts_out={"n": len(out)},
    )


@register("supplier_price_spike")
def supplier_price_spike(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    prev = [_prev_month(lm)]
    prev += [_prev_month(prev[-1]), _prev_month(_prev_month(prev[-1]))]
    rows = []
    for name, d in ((s.get("details") or {}).get("purchases") or {}).items():
        mo = d.get("months") or {}
        if lm not in mo:
            continue
        old = [_d(mo[m].get("price")) for m in prev if m in mo and _d(mo[m].get("price"))]
        if not old:
            continue
        o = sum(old, D0) / len(old)
        n = _d(mo[lm].get("price"))
        if o and n:
            rows.append((name, o, n, n / o - 1, (n - o) * _d(mo[lm].get("qty"))))
    up = sorted([r for r in rows if r[3] > Decimal("0.07")], key=lambda r: -r[4])
    if not up:
        top = max(rows, key=lambda r: r[3]) if rows else None
        verdict = "Keskin (>7%) oshgan mahsulot yo'q" + (
            f"; eng ko'p — {top[0]} {P(top[3])}." if top else "."
        )
        return card(
            item,
            verdict,
            [
                ("Oshgan mahsulotlar", "0", ">7%", "good"),
                ("Eng katta o'sish", P(top[3]) if top else "—", top[0] if top else "", ""),
                ("Oylik ta'sir", "0", "", ""),
            ],
            source=f"Kirim (birlik narxi, {lm})",
            live="Masalliq narxlari barqaror — keskin oshgan mahsulot yo'q.",
            ctx=ctx,
            facts_out={"n": 0},
        )
    t = up[0]
    imp = sum((r[4] for r in up), D0)
    verdict = f"{len(up)} mahsulot keskin oshdi: {t[0]} +{P(t[3])} (oyiga −{M(t[4])})."
    return card(
        item,
        verdict,
        [
            ("Oshgan mahsulotlar", str(len(up)), ">7% (3 oy o'rtachasiga)", "bad"),
            (
                "Eng katta o'sish",
                "+" + P(max(r[3] for r in up)),
                max(up, key=lambda r: r[3])[0],
                "bad",
            ),
            ("Oylik ta'sir", "−" + M(imp), "hajm × farq", "bad"),
        ],
        table=(
            ["Mahsulot", "Eski", "Yangi", "%", "Ta'sir"],
            [[r[0], N(r[1]), N(r[2]), "+" + P(r[3]), N(r[4])] for r in up[:10]],
        ),
        actions=[
            "Yetkazib beruvchi bilan gaplashing",
            "Muqobil taklif so'rang (N38)",
            "Kerak bo'lsa narxni moslang (N24)",
        ],
        source=f"Kirim (birlik narxi, {_mname(lm)} vs oldingi 3 oy)",
        live=f"{t[0]} narxi {uz.uz_number_words(int(t[3] * 100))} foiz oshdi.",
        ctx=ctx,
        facts_out={"n": len(up), "top": t[0]},
    )


@register("terminal_reconciliation")
def terminal_reconciliation(
    ctx: ToolContext, item: CatalogItem, p: dict[str, Any]
) -> dict[str, Any]:
    from django.db.models import Sum

    from apps.finance.models import Transaction

    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    rows = [r for r in _cash_rows(s) if r[0][:7] == lm[:7]]
    pos = sum((_d(r[4]) for r in rows), D0)
    m0 = date.fromisoformat(lm)
    m1 = (m0 + timedelta(days=32)).replace(day=1)
    bank = _d(
        Transaction.objects.filter(
            is_actual=True, direction="in", txn_date__gte=m0 + timedelta(days=1), txn_date__lte=m1
        )
        .filter(note__icontains="terminal")
        .aggregate(x=Sum("amount"))["x"]
    )
    fee = _out_item(s, "komissiya")
    if not bank:
        diff_txt = 'bank kirimi ("Terminal" izohli) Kassada topilmadi'
        verdict = f"{_mname(lm)}: POS terminal {M(pos)}; {diff_txt} — bank ko'chirmasi bilan solishtiring."
        return card(
            item,
            verdict,
            [
                ("POS terminal", M(pos), f"{len(rows)} smena", ""),
                ("Bankka tushgan", "—", "Kassa: terminal kirimi yo'q", ""),
                ("Komissiya", M(fee), "oyiga", ""),
            ],
            actions=[
                "Haftalik yarashtiring (bank ko'chirmasi)",
                "Farq bo'lsa bankka murojaat",
                "Komissiya tarifini tekshiring (N37)",
            ],
            source=f"Smena (Terminal, {_mname(lm)}), Kassa (Bank komissiyasi)",
            live="Terminal summasini bank ko'chirmasi bilan haftada bir solishtiring.",
            ctx=ctx,
            facts_out={"pos": M(pos)},
        )
    diff = pos - fee - bank
    verdict = f"{_mname(lm)}: POS {M(pos)}, bank {M(bank)}, komissiya {M(fee)} — farq {M(diff)}."
    return card(
        item,
        verdict,
        [
            ("POS terminal", M(pos), "", ""),
            ("Bankka tushgan", M(bank), "T+1", ""),
            ("Farq", M(diff), "komissiyadan keyin", "good" if abs(diff) < 100_000 else "bad"),
        ],
        source="Smena (Terminal), Kassa (bank kirimlari)",
        live="Terminal tushumlari bankka to'liq tushgan — farq faqat komissiya."
        if abs(diff) < 100_000
        else f"Terminal va bank orasida {say_mln(diff)} farq bor.",
        ctx=ctx,
        facts_out={"diff": M(diff)},
    )


@register("tax_calendar")
def tax_calendar(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    taxes = [
        o for o in f["obligations"] if o.category in ("tax", "soliq") or "soliq" in o.title.lower()
    ]
    months = [lm]
    for _ in range(5):
        months.insert(0, _prev_month(months[0]))
    rows = []
    for m in months:
        a = pl_value(s, "aylanma solig'i", m)
        soc = pl_value(s, "ijtimoiy soliq", m)
        tot_acc = _d(
            (
                ((s.get("reports") or {}).get("balans") or {}).get("hisoblangan soliqlar oy") or {}
            ).get(m)
        )
        jsh = max(D0, tot_acc - a - soc) if tot_acc else D0
        nm = (date.fromisoformat(m) + timedelta(days=32)).replace(day=20)
        rows.append((m, a, jsh, soc, nm))
    la = rows[-1]
    nxt = taxes[0] if taxes else None
    when = nxt.date if nxt else la[4]
    amt = _d(nxt.amount) if nxt else la[1] + la[2] + la[3]
    rev = _plv(s, "sof tushum")
    pct = (amt / rev) if rev else D0
    verdict = f"Keyingi to'lov {Dt(when)}: ~{M(amt)} (aylanma {M(la[1])} + ish haqi soliqlari {M(la[2] + la[3])})."
    return card(
        item,
        verdict,
        [
            ("Keyingi to'lov", M(amt), "", "bad" if amt > f["cash"] else ""),
            ("Sana", Dt(when), "har oy 20-sanagacha", ""),
            ("Joriy oy ajratma", M(amt / 30), f"kuniga (~{P(pct)} tushum)", ""),
        ],
        chart=_bar(
            "Oylik soliqlar", [_mname(r[0])[:3] for r in rows], [r[1] + r[2] + r[3] for r in rows]
        ),
        table=(
            ["Oy", "Aylanma", "JShDS", "Ijtimoiy", "To'lov sanasi"],
            [[_mname(r[0]), N(r[1]), N(r[2]), N(r[3]), Dt(r[4])] for r in rows],
        ),
        actions=[
            f"Har kuni tushumning ~{P(pct)} ini ajrating",
            "20-sanadan oldin katta xarid qilmang",
            "Soliq rejimini tekshiring (S25)",
        ],
        source="Foyda-zarar (aylanma, ijtimoiy soliq), Balans (hisoblangan soliqlar), to'lov kalendari",
        live=f"{when.day}-{uz.MONTHS[when.month - 1]}da {say_mln(amt)}ga yaqin soliq to'laysiz.",
        ctx=ctx,
        facts_out={"next": M(amt), "date": when.isoformat()},
    )


@register("seasonality_profile")
def seasonality_profile(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    seas = {int(k): _d(v) for k, v in ((s.get("details") or {}).get("seasonality") or {}).items()}
    fact = {
        int(k[5:7]): _d(v.get("revenue"))
        for k, v in (s.get("months") or {}).items()
        if k < last_month(s) or k == last_month(s)
    }
    if not seas and fact:
        mu = sum(fact.values(), D0) / len(fact)
        seas = {m: (v / mu).quantize(Decimal("0.01")) for m, v in fact.items()}
    if not seas:
        return card(item, "Mavsumiylik uchun ma'lumot kam.", [("—", "—", "", "")] * 3, ctx=ctx)
    hi = sorted(seas, key=lambda m: -seas[m])[:2]
    lo = min(seas, key=lambda m: seas[m])
    drop = seas[lo] / max(seas.values()) - 1
    hol = [
        r
        for r in _smena(s)
        if any(w in str(r[2]).lower() for w in ("bayram", "yil", "navro", "hayit"))
    ]
    avgc = sum((_d(r[1]) for r in _smena(s)), D0) / max(1, len(_smena(s)))
    hol_k = (sum((_d(r[1]) for r in hol), D0) / len(hol) / avgc - 1) if hol and avgc else D0
    names = " va ".join(uz.MONTHS[m - 1].capitalize() for m in hi)
    verdict = f"Eng yuqori — {names}, eng past — {uz.MONTHS[lo - 1].capitalize()} ({P(drop)})."
    return card(
        item,
        verdict,
        [
            (
                "Eng yuqori oy",
                uz.MONTHS[hi[0] - 1].capitalize(),
                f"indeks {str(seas[hi[0]]).replace('.', ',')}",
                "good",
            ),
            (
                "Eng past oy",
                uz.MONTHS[lo - 1].capitalize(),
                f"indeks {str(seas[lo]).replace('.', ',')}",
                "bad",
            ),
            (
                "Bayram ta'siri",
                (("+" if hol_k >= 0 else "") + P(hol_k)) if hol else "—",
                f"{len(hol)} bayram kuni (cheklar)",
                "",
            ),
        ],
        chart=_bar(
            "Oylik indeks",
            [uz.MONTHS[m - 1][:3].capitalize() for m in sorted(seas)],
            [seas[m] for m in sorted(seas)],
            "indeks",
            1,
        ),
        table=(
            ["Oy", "Indeks", "Fakt tushum"],
            [
                [
                    uz.MONTHS[m - 1].capitalize(),
                    str(seas[m]).replace(".", ","),
                    N(fact[m]) if m in fact else "—",
                ]
                for m in sorted(seas)
            ],
        ),
        actions=[
            "Past oyga aksiya rejalang (N07)",
            "Yuqori oyga zaxira va xodim",
            "Katta xarajatni yuqori oy oldidan qilmang",
        ],
        source="Fin reja (mavsum koeffitsientlari), Smena (oylik tushum, bayram izohlari)",
        live=f"{names} yuqori, {uz.MONTHS[lo - 1]} eng past.",
        ctx=ctx,
        facts_out={"high": hi, "low": lo},
    )


@register("mom_change")
def mom_change(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    m = last_month(s)
    pm = _prev_month(m)

    def k(key: str, mm: str) -> Decimal:
        return pl_value(s, key, mm)

    kp = [
        ("Tushum", "sof tushum", 1),
        ("Cheklar", "cheklar soni smena", 1),
        ("O'rtacha chek", "o'rtacha chek so'm", 1),
        ("Food cost %", "food cost sof tushumga", -1),
        ("Sof foyda", "sof foyda", 1),
    ]
    rows = [(lbl, k(key, pm), k(key, m), sign) for lbl, key, sign in kp]
    lab = (
        (k("ish haqi", pm) / k("sof tushum", pm), k("ish haqi", m) / k("sof tushum", m))
        if k("sof tushum", pm) and k("sof tushum", m)
        else (D0, D0)
    )
    rows.insert(4, ("Labor %", lab[0], lab[1], -1))

    def rel(r: tuple[str, Decimal, Decimal, int]) -> Decimal:
        if "%" in r[0]:
            return (r[2] - r[1]) * r[3] * 10
        return ((r[2] / r[1] - 1) * r[3]) if r[1] else D0

    good = [r[0] for r in rows[:-1] if rel(r) > Decimal("0.005")]
    bad = [r[0] for r in rows[:-1] if rel(r) < -Decimal("0.005")]
    dprof = rows[-1][2] - rows[-1][1]
    be = break_even(s, m)
    vol = (rows[1][2] - rows[1][1]) * rows[2][1] * be.cm_ratio
    price = (rows[2][2] - rows[2][1]) * rows[1][2] * be.cm_ratio
    other = dprof - vol - price

    def fmt(lbl: str, v: Decimal) -> str:
        return P(v) if "%" in lbl else (N(v) if "Cheklar" in lbl else M(v))

    sg = "+" if dprof >= 0 else ""
    verdict = f"{_mname(m)}: foyda {sg}{M(dprof)}; yaxshi — {', '.join(good) or 'yo‘q'}, yomon — {', '.join(bad) or 'yo‘q'}."
    return card(
        item,
        verdict,
        [
            (
                "Foyda o'zgarishi",
                sg + M(dprof),
                f"{_mname(pm)} → {_mname(m)}",
                "good" if dprof >= 0 else "bad",
            ),
            ("Eng yaxshi KPI", max(rows[:-1], key=rel)[0], "", "good"),
            ("Eng yomon KPI", min(rows[:-1], key=rel)[0], "", "bad"),
        ],
        chart={
            "type": "bar",
            "title": "Foyda o'zgarishi omillari (mln so'm)",
            "x": "omil",
            "y": "qiymat",
            "data": [
                {
                    "omil": lbl,
                    "qiymat": float((v / 1_000_000).quantize(Decimal("0.1"))),
                    "color": "#14B8A6" if v >= 0 else "#F87171",
                }
                for lbl, v in (
                    ("Mijozlar soni", vol),
                    ("O'rtacha chek", price),
                    ("Xarajatlar", other),
                )
            ],
        },
        table=(
            ["KPI", _mname(pm), _mname(m), "Δ"],
            [
                [
                    r[0],
                    fmt(r[0], r[1]),
                    fmt(r[0], r[2]),
                    (("+" if r[2] >= r[1] else "") + fmt(r[0], r[2] - r[1])),
                ]
                for r in rows
            ],
        ),
        actions=[
            f"Yomonlashgan KPI ({bad[0] if bad else '—'}) ga 1 chora",
            "Yaxshisini mustahkamlang",
            "Keyingi oy maqsadi (N42)",
        ],
        source=f"Foyda-zarar ({_mname(pm)}, {_mname(m)})",
        live=f"{_mname(m)} {_mname(pm).lower()}dan {'yaxshi' if dprof >= 0 else 'yomon'}: foyda {say_mln(dprof)} {'oshdi' if dprof >= 0 else 'kamaydi'}.",
        ctx=ctx,
        facts_out={"dprofit": M(dprof)},
    )


@register("partner_profit_split")
def partner_profit_split(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    pl = (s.get("reports") or {}).get("pl") or {}
    lm = last_month(s)
    yr = lm[:4]

    def ytd(key: str) -> Decimal:
        return sum(
            (_d(v) for kk, v in (pl.get(key) or {}).items() if kk.startswith(yr) and kk <= lm), D0
        )

    p1, p2 = ytd("sherik 1 foyda ulushi"), ytd("sherik 2 foyda ulushi")
    net = ytd("sof foyda")
    if not p1 and not p2:
        p1, p2 = net * Decimal("0.6"), net * Decimal("0.4")
    sh1 = p1 / (p1 + p2) if p1 + p2 else Decimal("0.6")
    div = ytd("olingan dividend")
    kir = ytd("kiritma yil davomida")
    d1, d2 = div * sh1, div * (1 - sh1)
    k1, k2 = kir * sh1, kir * (1 - sh1)
    r1, r2 = p1 + k1 - d1, p2 + k2 - d2
    verdict = f"Sherik 1: {M(r1)}, Sherik 2: {M(r2)} (yil boshidan, kiritma va dividend bilan)."
    return card(
        item,
        verdict,
        [
            ("Sherik 1 qoldig'i", M(r1), f"ulush {P(sh1)}", ""),
            ("Sherik 2 qoldig'i", M(r2), f"ulush {P(1 - sh1)}", ""),
            ("Olingan dividend", M(div), "yil boshidan", ""),
        ],
        chart=_bar("Sheriklar qoldig'i", ["Sherik 1", "Sherik 2"], [r1, r2]),
        table=(
            ["Sherik", "Ulush", "Foyda", "Kiritma", "Dividend", "Qoldiq"],
            [
                ["Sherik 1", P(sh1), N(p1), N(k1), N(d1), N(r1)],
                ["Sherik 2", P(1 - sh1), N(p2), N(k2), N(d2), N(r2)],
            ],
        ),
        actions=[
            "Dividendni xavfsiz summada oling (N14)",
            "Kiritmalarni hisobga oling",
            "Yozma kelishuv tuzing",
        ],
        assumptions="Kiritma va dividend ulush nisbatida bo'lingan (faylda sherik bo'yicha ajratilmagan).",
        source="Foyda-zarar (Sherik 1/2 foyda ulushi, Olingan dividend, Kiritma)",
        live=f"Yil boshidan Sherik birga {say_mln(r1)}, Sherik ikkiga {say_mln(r2)} to'g'ri keladi.",
        ctx=ctx,
        facts_out={"p1": M(r1), "p2": M(r2)},
    )


@register("risk_map")
def risk_map(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    be = break_even(s, lm)
    rev = _plv(s, "sof tushum")
    risks = []
    risks.append(
        (
            "Mijozlar oqimi −20%",
            "o'rta",
            rev * Decimal("0.2") * be.cm_ratio * 3,
            "1 oylik zaxira (N04)",
        )
    )
    gap = f["buffer"] - f["min_balance"]
    risks.append(
        (
            "Kassa tang kuni",
            "yuqori" if gap > 0 else "past",
            max(gap, D0) + f["buffer"] * (1 if gap > 0 else 0),
            f"{Dt(f['min_date'])} oldidan katta xarid qilmang",
        )
    )
    _m, rows = _staff(s, "oshpaz")
    sal = max((r["total"] for r in rows), default=Decimal(5_000_000))
    risks.append(
        (
            "Kalit kadr (bosh oshpaz)",
            "o'rta",
            sal * Decimal("1.5") + rev * Decimal("0.05") * be.cm_ratio * 2,
            "o'rinbosar + texkarta",
        )
    )
    pur = (s.get("details") or {}).get("purchases") or {}
    tot = {n: _d(((d.get("months") or {}).get(lm) or {}).get("amount")) for n, d in pur.items()}
    top = max(tot, key=lambda n: tot[n]) if tot else "—"
    risks.append(
        (
            f"Xom ashyo narxi ({top})",
            "o'rta",
            tot.get(top, D0) * Decimal("0.15") * 3,
            "muqobil ta'minotchi, narx moslash",
        )
    )
    ch = (((s.get("details") or {}).get("channels") or {}).get("months") or {}).get(lm, {})
    agg = sum((_d(v["revenue"]) for v in ch.values() if _d(v.get("commission"))), D0)
    risks.append(
        (
            "Agregatorga bog'liqlik",
            "past" if agg / rev < Decimal("0.25") else "o'rta",
            agg * Decimal("0.3") * be.cm_ratio * 3 if rev else D0,
            "o'z dostavkani kuchaytiring (Q1)",
        )
    )
    if f["loan"]:
        risks.append(
            (
                "Kredit to'lovi",
                "past",
                f["loan"]["principal"] * 3,
                "kredit kalendarini kuzating (N03)",
            )
        )
    w = {"yuqori": 3, "o'rta": 2, "past": 1}
    risks.sort(key=lambda r: -(w[r[1]] * r[2]))
    t = risks[:3]
    verdict = (
        f"Top-3 xavf: {t[0][0]}, {t[1][0]}, {t[2][0]}. Eng katta zarar — {t[0][0]} ({M(t[0][2])})."
    )
    return card(
        item,
        verdict,
        [
            ("Eng katta xavf", t[0][0], "", "bad"),
            ("Ehtimol", t[0][1], "", ""),
            ("Ta'sir", M(t[0][2]), "3 oy ichida", "bad"),
        ],
        table=(
            ["Xavf", "Ehtimol", "Ta'sir (3 oy)", "Himoya"],
            [[r[0], r[1], N(r[2]), r[3]] for r in risks],
        ),
        actions=[
            "Har xavfga 1 himoya",
            f"Zaxira: kamida {M(f['buffer'])} (N04)",
            "Choraklik qayta ko'rib chiqish",
        ],
        assumptions="Ta'sir — 3 oylik zarar (yalpi marja bo'yicha), ehtimol — sifat bahosi.",
        source="Foyda-zarar, Kunlik prognoz, Ish haqi, Kirim, Sotuv kanallari, Kontragentlar",
        live=f"Eng katta xavf — {t[0][0].lower()}; zaxira sizni himoya qiladi.",
        ctx=ctx,
        facts_out={"top": t[0][0]},
    )


@register("insurance")
def insurance(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    lm = last_month(s)
    fixed_assets = _d(
        (
            ((s.get("reports") or {}).get("balans") or {}).get("asosiy vositalar qoldiq qiymati")
            or {}
        ).get(lm)
    )
    if not fixed_assets:
        fixed_assets = sum(
            (_d(a.get("value")) for a in (s.get("details") or {}).get("assets") or []), D0
        )
    stock = _d(
        (((s.get("reports") or {}).get("balans") or {}).get("tovar moddiy zaxiralar") or {}).get(lm)
    )
    be = break_even(s, lm)
    downtime = be.fixed
    val = fixed_assets + stock + downtime
    prem = _d(p.get("amount")) or (fixed_assets + stock) * Decimal("0.006")
    pct = prem / val if val else D0
    ok = pct <= Decimal("0.01")
    verdict = f"Himoya qiymati ~{M(val)}; badal ~{M(prem)}/yil ({P(pct)}) — {'arziydi' if ok else 'qimmat, takliflarni solishtiring'}."
    return card(
        item,
        verdict,
        [
            ("Himoya qiymati", M(val), "vositalar + zaxira + 1 oy to'xtash", ""),
            ("Yillik badal", M(prem), "taxmin 0,6%" if not p.get("amount") else "siz bergan", ""),
            ("Badal %", P(pct), "≤ 1% — arziydi", "good" if ok else "bad"),
        ],
        table=(
            ["Xavf", "Zarar", "Qoplanadimi"],
            [
                ["Yong'in / suv bosishi", N(fixed_assets), "ha (mulk polisi)"],
                ["Zaxira buzilishi", N(stock), "ha (kengaytirilgan)"],
                ["To'xtash (1 oy)", N(downtime), "faqat qo'shimcha band bilan"],
            ],
        ),
        actions=[
            "Asosiy vositalarni sug'urtalang",
            "To'xtash zararini qo'shing",
            "2–3 kompaniya taklifini solishtiring",
        ],
        assumptions="Badal mulk qiymatining ~0,6% i (O'zbekiston bozori, taxmin; aniq narx — sug'urtachidan).",
        source=f"Balans (asosiy vositalar, zaxira, {_mname(lm)}), Foyda-zarar (doimiy xarajat)",
        live=f"Uskuna va zaxiralaringiz {say_mln(fixed_assets + stock)} turadi — yillik badal arzon bo'lsa, sug'urta arziydi.",
        ctx=ctx,
        facts_out={"value": M(val)},
    )


@register("urgent_actions")
def urgent_actions(ctx: ToolContext, item: CatalogItem, p: dict[str, Any]) -> dict[str, Any]:
    f = facts(ctx)
    s = f["s"]
    acts: list[tuple[date, str, Decimal, str]] = []
    first = None
    if f["min_date"] and f["min_date"] <= f["today"] + timedelta(days=45):
        first = (
            f["min_date"],
            f"{Dt(f['min_date'])}gacha katta xarid qilmaslik",
            f["cash"] - f["min_balance"],
            f"eng tang kun: {M(f['min_balance'])}",
        )
    big = sorted(
        [o for o in f["obligations"] if o.date <= f["today"] + timedelta(days=14)],
        key=lambda o: -_d(o.amount),
    )[:3]
    for o in big:
        acts.append((o.date, f"{o.title} uchun pul tayyorlash", _d(o.amount), "to'lov"))
    lm = last_month(s)
    for name, d in ((s.get("details") or {}).get("purchases") or {}).items():
        mo = d.get("months") or {}
        pm = _prev_month(lm)
        if lm in mo and pm in mo and _d(mo[pm].get("price")):
            g = _d(mo[lm].get("price")) / _d(mo[pm].get("price")) - 1
            imp = (_d(mo[lm].get("price")) - _d(mo[pm].get("price"))) * _d(mo[lm].get("qty"))
            if g > Decimal("0.1") and imp >= 1_000_000:
                acts.append(
                    (
                        f["today"] + timedelta(days=3),
                        f"{name} narxi +{P(g)} — ta'minotchi bilan gaplashish",
                        (_d(mo[lm].get("price")) - _d(mo[pm].get("price"))) * _d(mo[lm].get("qty")),
                        "narx",
                    )
                )
    acts.sort(key=lambda a: (a[0], -a[2]))
    top = ([first] if first else []) + acts[: 3 - (1 if first else 0)]
    if not top:
        return card(
            item,
            "Shoshilinch ish yo'q — kassa xavfsiz, 14 kunda katta to'lov yo'q.",
            [("1-ish", "—", "", "good"), ("Muddat", "—", "", ""), ("Pul ta'siri", "0", "", "")],
            ctx=ctx,
        )
    verdict = " ".join(f"{i + 1}) {a[1]} — {Dt(a[0])}, {M(a[2])}." for i, a in enumerate(top))
    return card(
        item,
        verdict,
        [
            ("1-ish", top[0][1], top[0][3], "bad"),
            ("Muddat", Dt(top[0][0]), "", ""),
            ("Pul ta'siri", M(top[0][2]), "", ""),
        ],
        table=(
            ["Ish", "Muddat", "Ta'sir", "Holat"],
            [[a[1], Dt(a[0]), N(a[2]), "kutilmoqda"] for a in top],
        ),
        actions=["Birinchisini bugun", "Qolganlarini Vazifalarga", "Haftalik qayta ko'rib chiqish"],
        source="Kunlik prognoz, to'lov kalendari, Kirim (narxlar)",
        live=f"Birinchi navbatda — {top[0][1].lower()}.",
        ctx=ctx,
        facts_out={"first": top[0][1]},
    )

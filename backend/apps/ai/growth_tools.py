"""Chat/Live tools for the growth CFO: growth_plan (P1) and evaluate_investment (P2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.engine import growth as G
from apps.tenancy.context import today_for

from . import uz_format as uz
from .tools import TOOLS, Tool, ToolContext, envelope, speech_of

D0 = Decimal(0)


def M(x: Decimal) -> str:
    x = Decimal(x)
    return uz.format_som(x.quantize(Decimal(1))) if abs(x) < 1_000_000 else uz.format_mln(x)


def P(x: Decimal) -> str:
    return f"{(Decimal(x) * 100).quantize(Decimal('0.1'))}%".replace(".", ",")


def Dt(d: date | None) -> str:
    return f"{d.day}-{uz.MONTHS[d.month - 1].lower()} {d.year}" if d else "—"


def _summary() -> dict[str, Any] | None:
    from apps.integrations.models import DataSource

    src = DataSource.objects.exclude(summary={}).first()
    s = src.summary if src else None
    return s if s and s.get("reports", {}).get("pl") and s.get("details") else None


def _no_data() -> dict[str, Any]:
    md = "**Bu tahlil uchun Foyda-zarar va Menyu ma'lumotlari kerak — jadvalingizda topilmadi.**"
    return envelope(
        ok=True,
        facts={},
        md=md,
        say=md.strip("*"),
        answer={"headline": md.strip("*"), "reason": ""},
    )


def _fc(ctx: ToolContext) -> tuple[Decimal, Decimal | None, date | None, Decimal]:
    base = ctx.base
    n = min(90, base.horizon_days)
    closes = [Decimal(str(base.close_on(base.date_at(i)))) for i in range(n)]
    i_min = min(range(n), key=lambda i: closes[i])
    cash = closes[0]
    return cash, closes[i_min], base.date_at(i_min), Decimal(base.safe_min)


def growth_plan_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    cash, fmin, fdate, safe = _fc(ctx)
    g = G.growth_plan(s, forecast_min=fmin, safe_min=safe, cash=cash)
    top = g.levers[: int(args.get("top") or 10)]
    new_lo, new_hi = g.net_profit + g.uplift_lo, g.net_profit + g.uplift_hi
    head = (
        f"**{g.verdict}: kassa xavfsiz ({M(cash)}, 90 kunda eng kami {M(fmin or cash)}), "
        f"lekin foydani oyiga +{M(g.uplift_lo)} … +{M(g.uplift_hi)} oshirish mumkin — sof foyda {M(g.net_profit)} → {M(new_lo)}–{M(new_hi)}.**"
    )
    pt = g.profit_trend[-4:]
    fc0, fc1 = (g.food_cost[0], g.food_cost[-1]) if g.food_cost else (None, None)
    lines = [head, "", "### Nima uchun"]
    lines.append(
        "- Sof foyda (oxirgi oylar): "
        + ", ".join(f"{uz.MONTHS[int(m[5:7]) - 1][:3]} {M(v)}" for m, v in pt)
        + "."
    )
    if fc0 and fc1:
        lines.append(
            f"- Food cost {P(fc0[1])} (yanvar) → {P(fc1[1])} (oxirgi oy), maqsad {P(g.fc_target)}: oyiga ~{M(g.fc_leak)} yo'qotish."
        )
    if g.inflation:
        lines.append(
            "- Xomashyo narxi yil boshidan: "
            + ", ".join(f"{n} +{P(c)}" for n, c, _ in g.inflation[:4])
            + "; menyu narxlari o'zgarmagan."
        )
    if len(g.weekdays) == 7:
        mn, mx = min(g.weekdays, key=lambda w: w[1]), max(g.weekdays, key=lambda w: w[1])
        lines.append(
            f"- Hafta kunlari: {mn[0]} {M(mn[1])} vs {mx[0]} {M(mx[1])}; cheklar rejaga nisbatan {P(g.checks_vs_plan)}, o'rtacha chek {'+' if g.avg_check_vs_plan >= 0 else ''}{P(g.avg_check_vs_plan)}."
        )
    lines.append(
        f"- Bo'sh pul: {M(g.idle_cash)} (zaxira 3 oylik doimiy xarajat {M(g.reserve)} qoldirilgan); kredit {M(g.loan_balance)} @{P(g.loan_rate)}."
    )
    lines += [
        "",
        "### O'sish rejasi (oyiga foyda ta'siri)",
        "| # | Harakat | Oyiga foyda | Ishonch |",
        "|---|---|---|---|",
    ]
    for i, lv in enumerate(top, 1):
        lines.append(f"| {i} | {lv.title} | +{M(lv.lo)} … +{M(lv.hi)} | {lv.confidence} |")
    lines.append(f"| | **Jami** | **+{M(g.uplift_lo)} … +{M(g.uplift_hi)}** | |")
    lines += ["", "### Qanday qilish"]
    for i, lv in enumerate(top, 1):
        lines.append(
            f"{i}. **{lv.title}** — "
            + "; ".join(lv.steps)
            + f". _Taxmin: {'; '.join(lv.assumptions)}._"
        )
    lines += [
        "",
        "### Menyu tahlili",
        "| Taom | Sotildi | Porsiya foydasi | Food cost | Sinf |",
        "|---|---|---|---|---|",
    ]
    for x in g.dishes:
        lines.append(
            f"| {x.name} | {uz.group_digits(int(x.sold))} | {M(x.margin)} | {P(x.fc)} | {x.cls} |"
        )
    lines += [
        "",
        "CHIPS: Narxlarni qanday oshiray? | 30 mln ga fritur olsam? | Kreditni yopsam-chi?",
    ]
    facts: dict[str, Any] = {
        "verdict": g.verdict,
        "cash": M(cash),
        "forecast_min": M(fmin or cash),
        "net_profit": M(g.net_profit),
        "uplift_lo": M(g.uplift_lo),
        "uplift_hi": M(g.uplift_hi),
        "new_profit_lo": M(new_lo),
        "new_profit_hi": M(new_hi),
        "fc_leak": M(g.fc_leak),
        "reserve": M(g.reserve),
        "idle_cash": M(g.idle_cash),
    }
    for i, lv in enumerate(top):
        facts[f"lever{i}_lo"], facts[f"lever{i}_hi"] = M(lv.lo), M(lv.hi)
    md = "\n".join(lines)
    return envelope(
        ok=True,
        facts=facts,
        speech=speech_of(facts),
        md=md,
        say=head.strip("*"),
        answer={"headline": head.strip("*"), "reason": g.verdict_reason},
        levers=[
            {
                "title": lv.title,
                "lo": M(lv.lo),
                "hi": M(lv.hi),
                "steps": lv.steps,
                "confidence": lv.confidence,
            }
            for lv in g.levers
        ],
    )


ITEM_DISH = {
    "fritur": "fri",
    "fri": "fri",
    "gril": "burger",
    "pech": "burger",
    "kofe": "amerikano",
    "kofemashina": "amerikano",
    "plita": "osh",
    "qozon": "osh",
}


def evaluate_investment_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = _summary()
    if s is None:
        return _no_data()
    price = Decimal(args["price"])
    item = str(args.get("item") or "uskuna")
    menu = s["details"].get("menu", {})
    dish = args.get("dish")
    if not dish:
        key = next((v for k, v in ITEM_DISH.items() if k in item.lower()), None)
        dish = next((n for n in menu if key and key in n.lower()), None)
    dish = next((n for n in menu if dish and dish.lower() in n.lower()), None) if dish else None
    if not dish and not args.get("unit_margin"):
        md = (
            f"**{item} qaysi taomni ko'paytiradi?** Shuni ayting — foyda va qoplanishni hisoblayman.\n\nCHIPS: "
            + " | ".join(list(menu)[:3])
        )
        return envelope(
            ok=True,
            facts={},
            md=md,
            say=md.split("\n")[0].strip("*"),
            answer={"headline": f"{item} qaysi taom uchun?", "reason": ""},
        )
    d = menu.get(dish, {}) if dish else {}
    margin = Decimal(
        str(args.get("unit_margin") or (Decimal(d.get("price", 0)) - Decimal(d.get("cost", 0))))
    )
    m = G.last_month(s)
    sold_day = (
        (Decimal(str((d.get("sold") or {}).get(m, 0))) / 30).quantize(Decimal(1)) if d else D0
    )
    assumed = args.get("extra_units_per_day") is None
    units = Decimal(str(args.get("extra_units_per_day") or max(10, int(sold_day * Decimal("0.3")))))
    opex = Decimal(str(args.get("extra_opex_month") or 1_500_000))
    cash, fmin, fdate, safe = _fc(ctx)
    be = G.break_even(s, m)
    buffer = max(safe, (be.fixed * 3).quantize(Decimal(1)) if args.get("strict_buffer") else safe)
    reserve = (be.fixed * 3).quantize(Decimal(1))
    buffer = max(safe, reserve)
    loan = s.get("loan") or {}
    rate = Decimal(str(loan.get("rate_pct") or 24)) / 100
    base_net = G.pl_value(s, "sof foyda", m)
    r = G.evaluate_investment(
        price,
        units,
        margin,
        extra_opex=opex,
        today=today_for(ctx.business),
        cash=cash,
        forecast_min=fmin,
        forecast_min_date=fdate,
        buffer=buffer,
        base_net=base_net,
        rate=rate,
        life_months=int(args.get("life_months") or 60),
    )
    cons = G.evaluate_investment(
        price, (units * Decimal("0.7")).quantize(Decimal(1)), margin, extra_opex=opex, rate=rate
    )
    vword = {"OLING": "Ha, oling", "KUTING": "Hozir kuting", "OLMANG": "Olmang"}[r.verdict]
    when = (
        f" — eng yaxshi vaqt: {Dt(r.best_date)}gacha (dekabr mavsumidan oldin)"
        if r.best_date
        else ""
    )
    head = f"**{vword}{when}. {M(price)} to'laysiz, {str(r.payback_months or '—').replace('.', ',')} oyda o'zini qoplaydi, 12 oyda +{M(r.profit_12)} sof foyda.**".replace(
        ",0 oyda", " oyda"
    )
    lines = [head, "", "### Foyda (asosiy ko'rsatkich)"]
    lines.append(
        f"- «{dish or item}»: porsiya foydasi {M(margin)}; qo'shimcha {int(units)} porsiya/kun{' (taxmin: hozirgi ' + str(int(sold_day)) + '/kun sotuvning ~30%)' if assumed else ''}."
    )
    lines.append(
        f"- Oylik qo'shimcha foyda: 1-oy {M(r.monthly[0])}, 2-oy {M(r.monthly[1])}, 3-oydan {M(r.monthly[2])} (ishga tushish 50/75/100%, xarajat {M(opex)}/oy)."
    )
    lines.append(
        f"- Amortizatsiya {M(r.depreciation)}/oy — foydadan ayriladi; pulning o'zi zarar emas, uskunaga aylanadi."
    )
    lines.append(
        f"- 12 oy: +{M(r.profit_12)} (ROI {r.roi_12}%), 24 oy: +{M(r.profit_24)}; NPV ({P(rate)}): {M(r.npv)}."
    )
    lines += ["", "### Kassa (cheklov)"]
    lines.append(
        f"- Kassa {M(cash)} → xariddan keyin {M(r.cash_after)}; 90 kundagi eng past nuqta {M(r.cash_low)} ({Dt(fdate)})."
    )
    lines.append(
        f"- Xavfsiz chegara (3 oylik doimiy xarajat): {M(buffer)} — {'yuqorida qoladi ✓' if r.cash_low >= buffer else 'pastga tushadi ✗'}."
    )
    lines += [
        "",
        "### Xavf",
        f"- Talab 30% kam bo'lsa ham qoplanish {str(cons.payback_months or '—').replace('.', ',')} oy.",
        f"- Zararsizlik: kuniga kamida {str(r.breakeven_units).replace('.', ',')} porsiya (foydali muddatning yarmida qoplash uchun).",
    ]
    lines += [
        "",
        "### Moliyalash",
        f"- O'z pulingiz bilan: bo'sh pul yetarli. Kredit {P(rate)} bilan olsangiz, 12 oyda ~{M(r.loan_cost)} foiz — bu yerda qimmat.",
        "",
        "### Tavsiyam",
    ]
    lines.append(
        f"{vword}: {r.reason}. Qo'shimcha sotuvni (porsiyalarni) alohida yozib boring — 1-oy oxirida taxminni tekshiramiz."
    )
    if assumed:
        lines += [
            "",
            "### Menga kerak",
            f"- Uskuna kuniga nechta qo'shimcha porsiya beradi (men {int(units)} deb oldim)?",
        ]
    lines += [
        "",
        "CHIPS: Kuniga 50 porsiya bo'lsa? | Kreditga olsam-chi? | Narxini internetdan top",
    ]
    pts = lambda vals: [
        {"label": str(i + 1), "value": int(v), "display": M(v)} for i, v in enumerate(vals)
    ]
    pb = (
        int(r.payback_months.to_integral_value(rounding="ROUND_CEILING"))
        if r.payback_months
        else None
    )
    blocks = [
        {
            "type": "payback_chart",
            "id": "jcurve",
            "title": "Jamg'arilgan foyda: investitsiya bilan / siz (oylar)",
            "points": pts([a - b for a, b in zip(r.cum_with, r.cum_without, strict=True)]),
            "break_even_index": pb,
            "break_even_label": f"{r.payback_months} oyda o'zini qoplaydi" if pb else "",
            "series": [
                {
                    "name": "Investitsiya bilan (qo'shimcha)",
                    "points": pts(
                        [
                            sum(r.monthly[: i + 1], D0) - price - r.depreciation * 0
                            for i in range(24)
                        ]
                    ),
                },
                {
                    "name": "Talab −30%",
                    "points": pts([sum(cons.monthly[: i + 1], D0) - price for i in range(24)]),
                },
            ],
        },
        {
            "type": "scenario_table",
            "id": "inv_cases",
            "title": "Foyda va kassa",
            "columns": ["Asosiy", "Talab −30%"],
            "highlight": 0,
            "rows": [
                {"label": "Oylik foyda (3-oydan)", "values": [M(r.monthly[2]), M(cons.monthly[2])]},
                {
                    "label": "Qoplanish",
                    "values": [
                        f"{r.payback_months} oy",
                        f"{cons.payback_months} oy" if cons.payback_months else "yo'q",
                    ],
                },
                {"label": "12 oy sof foyda", "values": [M(r.profit_12), M(cons.profit_12)]},
                {"label": "Kassa eng past nuqta", "values": [M(r.cash_low), M(r.cash_low)]},
            ],
        },
    ]
    facts = {
        "verdict": r.verdict,
        "price": M(price),
        "payback": str(r.payback_months),
        "profit_12": M(r.profit_12),
        "profit_24": M(r.profit_24),
        "npv": M(r.npv),
        "cash_after": M(r.cash_after),
        "cash_low": M(r.cash_low),
        "buffer": M(buffer),
        "month1": M(r.monthly[0]),
        "month2": M(r.monthly[1]),
        "month3": M(r.monthly[2]),
        "margin": M(margin),
        "units": str(int(units)),
        "best_date": r.best_date.isoformat() if r.best_date else None,
        "downside_payback": str(cons.payback_months),
        "depreciation": M(r.depreciation),
        "loan_cost": M(r.loan_cost),
    }
    md = "\n".join(lines)
    return envelope(
        ok=True,
        facts=facts,
        speech=speech_of(facts),
        md=md,
        say=head.strip("*"),
        ui_blocks=blocks,
        answer={"headline": head.strip("*"), "reason": r.reason},
    )


GROWTH_TOOLS = [
    Tool(
        "growth_plan",
        "O'sish CFO: verdikt (XAVFLI/E'TIBOR/BARQAROR/O'SISH), foyda trendi, food cost, menyu tahlili, hafta kunlari va foydani oshirish rejasi (har harakat oyiga +X mln). 'Nima qilish kerak', 'foydani qanday oshiraman', 'biznesim qanday' savollari uchun.",
        {"type": "object", "properties": {"top": {"type": "integer", "minimum": 1, "maximum": 10}}},
        growth_plan_tool,
    ),
    Tool(
        "evaluate_investment",
        "Uskuna/investitsiya (narx ma'lum): foyda (oylik, 12/24 oy, qoplanish, NPV) + kassa (eng past nuqta, chegara) + vaqt + moliyalash + xavf; verdikt OLING/KUTING/OLMANG.",
        {
            "type": "object",
            "properties": {
                "price": {"type": "integer", "minimum": 1, "description": "Narx so'mda"},
                "item": {"type": "string", "maxLength": 80},
                "dish": {"type": "string", "maxLength": 80},
                "extra_units_per_day": {"type": "integer", "minimum": 1, "maximum": 10000},
                "unit_margin": {"type": "integer", "minimum": 1},
                "extra_opex_month": {"type": "integer", "minimum": 0},
                "life_months": {"type": "integer", "minimum": 6, "maximum": 120},
            },
            "required": ["price"],
        },
        evaluate_investment_tool,
    ),
]
TOOLS.update({t.name: t for t in GROWTH_TOOLS})

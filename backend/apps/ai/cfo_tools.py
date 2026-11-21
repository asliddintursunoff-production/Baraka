"""CFO analysis tools (Part C): apps/engine/cfo.py results as tool envelopes.

Each tool returns facts (numbers for the fact guard), display strings, a ready Uzbek markdown
paragraph `md` (used verbatim when the LLM is unavailable), cards with a one-line caption,
and the source of every figure. Workbooks without their own reports get a plain explanation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.engine import cfo
from apps.finance.models import CashAccount
from apps.integrations.models import DataSource

from . import uz_format as uz
from .tools import TOOLS, Tool, ToolContext, envelope

M = uz.format_mln
WD = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")


def P(x: Decimal, digits: str = "0.1") -> str:
    return f"{(x * 100).quantize(Decimal(digits))}".replace(".", ",") + "%"


def month_name(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{uz.MONTHS[d.month - 1]} {d.year}"


def summary_of(ctx: ToolContext) -> dict[str, Any] | None:
    src = DataSource.objects.exclude(summary={}).first()
    s = src.summary if src else None
    return s if s and s.get("reports", {}).get("pl") else None


def no_reports() -> dict[str, Any]:
    text = (
        "Bu tahlil uchun faylda **Foyda-zarar** va **Reja-fakt** hisobotlari kerak. Hozirgi jadvalingizda ular yo'q, "
        "shuning uchun faqat kassa va to'lovlar bo'yicha javob bera olaman."
    )
    return envelope(
        ok=True,
        md=text,
        say=text,
        answer={"verdict": "info", "headline": "Hisobotlar yo'q", "reason": text, "steps": []},
    )


def _done(
    facts: dict[str, Any], md: str, blocks: list[dict[str, Any]], say: str, headline: str
) -> dict[str, Any]:
    return envelope(
        ok=True,
        facts=facts,
        md=md,
        say=say,
        ui_blocks=blocks,
        answer={
            "verdict": "info",
            "headline": headline,
            "reason": md.split("\n")[0][:300],
            "steps": [],
        },
    )


def break_even_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    b = cfo.break_even(s, args.get("month"))
    mn = month_name(b.month)
    md = (
        f"{mn.capitalize()}da har 100 so'm savdodan **{P(b.cm_ratio)}** qoladi (o'zgaruvchan xarajatlar: mahsulot, agregator komissiyasi, "
        f"qadoq, bank, aylanma soliq). Doimiy xarajatlar oyiga **{M(b.fixed)}**. Zararsizlik nuqtasi: oyiga **{M(b.be_revenue)}** savdo, "
        f"ya'ni kuniga ~**{b.be_checks_per_day.quantize(Decimal(1))} chek** (kredit asosiy qarzi bilan ~**{b.cash_be_checks_per_day.quantize(Decimal(1))}**). "
        f"Hozir kuniga **{b.checks_per_day.quantize(Decimal(1))} chek** — zaxira katta."
    )
    blocks = [
        {
            "type": "metric_grid",
            "id": "break_even",
            "title": f"Zararsizlik · {mn}",
            "caption": "Kuniga nechta chek qilsangiz zarar ko'rmaysiz — hozirgi bilan solishtiring.",
            "items": [
                {"label": "Marja (CM)", "value": P(b.cm_ratio), "tone": "muted"},
                {"label": "Doimiy xarajat", "value": M(b.fixed), "note": "oyiga", "tone": "muted"},
                {
                    "label": "Zararsizlik",
                    "value": f"{b.be_checks_per_day.quantize(Decimal(1))} chek/kun",
                    "note": M(b.be_revenue) + "/oy",
                    "tone": "warn",
                },
                {
                    "label": "Kredit bilan",
                    "value": f"{b.cash_be_checks_per_day.quantize(Decimal(1))} chek/kun",
                    "tone": "warn",
                },
                {
                    "label": "Hozir",
                    "value": f"{b.checks_per_day.quantize(Decimal(1))} chek/kun",
                    "tone": "success",
                },
            ],
        }
    ]
    facts = {
        "month": b.month,
        "cm_pct": P(b.cm_ratio),
        "fixed": M(b.fixed),
        "be_revenue": M(b.be_revenue),
        "be_checks_per_day": str(b.be_checks_per_day.quantize(Decimal(1))),
        "cash_be_checks_per_day": str(b.cash_be_checks_per_day.quantize(Decimal(1))),
        "checks_per_day": str(b.checks_per_day.quantize(Decimal(1))),
        "avg_check": uz.format_som(b.avg_check.quantize(Decimal(1))),
        "source": "Foyda-zarar hisoboti + Smena",
    }
    return _done(
        facts,
        md,
        blocks,
        f"Kuniga taxminan {b.be_checks_per_day.quantize(Decimal(1))} chek qilsangiz zarar ko'rmaysiz, hozir {b.checks_per_day.quantize(Decimal(1))} ta.",
        f"Zararsizlik: kuniga ~{b.be_checks_per_day.quantize(Decimal(1))} chek",
    )


def stress_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    drops = tuple(int(x) for x in (args.get("drops") or (10, 20, 30, 40)))
    st = cfo.stress_test(s, drops, args.get("month"))
    lines = "\n".join(f"| −{d}% | {('+' if r >= 0 else '')}{M(r)} |" for d, r in st.drops)
    md = (
        f"Hozirgi oyda biznes oyiga **{M(st.base_result)}** sof pul ishlab chiqaradi (kredit asosiy qarzi to'langandan keyin). "
        f"Savdo tushganda oylik natija:\n\n| Savdo | Oyiga pul |\n|---|---|\n{lines}\n\n"
        f"Pul yo'qotish faqat savdo **~{st.max_drop_pct.quantize(Decimal(1))}%** dan ko'p tushganda boshlanadi."
    )
    blocks = [
        {
            "type": "scenario_table",
            "id": "stress",
            "title": "Savdo tushsa — oylik pul natijasi",
            "caption": "Qaysi tushishda oylik natija minusga o'tishini ko'ring.",
            "columns": [f"−{d}%" for d, _ in st.drops],
            "rows": [{"label": "Oyiga", "values": [M(r) for _, r in st.drops]}],
        }
    ]
    facts = {
        "drops": {f"-{d}%": M(r) for d, r in st.drops},
        "max_drop_pct": str(st.max_drop_pct.quantize(Decimal(1))),
        "base_result": M(st.base_result),
    }
    return _done(
        facts,
        md,
        blocks,
        f"Savdo {st.max_drop_pct.quantize(Decimal(1))} foizdan ko'p tushsagina oylik natija minusga o'tadi.",
        f"Savdo ~{st.max_drop_pct.quantize(Decimal(1))}% gacha tushsa ham pul yo'qotmaysiz",
    )


def cash_sources_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    cash = CashAccount.objects.order_by("-as_of_date").first()
    c = cfo.cash_sources(s, Decimal(cash.opening_balance) if cash else Decimal(0))
    period = f"{month_name(c.first_month)} – {month_name(c.last_month)}"
    md = (
        f"Kassadagi **{M(c.closing)}** qayerdan ({period}): boshlang'ich qoldiq **{M(c.opening)}**, biznesning o'zi (operatsion) "
        f"**+{M(c.operating)}**, ta'sischi kiritmasi **{M(c.owner_in)}**, kredit **{M(c.loan_in)}**; asosiy vositalarga **{M(-c.investing)}** sarflandi, "
        f"kredit qaytarildi **{M(-c.loan_repaid)}**, foiz **{M(-c.interest)}**"
        + (f", dividend **{M(-c.dividend)}**" if c.dividend else "")
        + ". "
        f"Kassaning ~**{P(c.external_share, '1')}** qismi ta'sischi va kredit puli — uni biznes ishlab topgan pul deb o'ylamang."
    )
    blocks = [
        {
            "type": "metric_grid",
            "id": "cash_sources",
            "title": f"Pul manbai · {period}",
            "caption": "Kassadagi pulning qancha qismi biznesdan, qanchasi ta'sischi va kreditdan.",
            "items": [
                {"label": "Operatsion (biznes)", "value": M(c.operating), "tone": "success"},
                {"label": "Investitsiya", "value": M(c.investing), "tone": "muted"},
                {
                    "label": "Moliyaviy",
                    "value": M(c.financing),
                    "note": f"ta'sischi {M(c.owner_in)}, kredit {M(c.loan_in)}",
                    "tone": "warn",
                },
                {"label": "Kassa", "value": M(c.closing), "tone": "muted"},
            ],
        }
    ]
    facts = {
        "period": period,
        "opening": M(c.opening),
        "operating": M(c.operating),
        "investing": M(c.investing),
        "financing": M(c.financing),
        "owner_in": M(c.owner_in),
        "loan_in": M(c.loan_in),
        "loan_repaid": M(c.loan_repaid),
        "interest": M(c.interest),
        "dividend": M(c.dividend),
        "closing": M(c.closing),
        "external_share": P(c.external_share, "1"),
    }
    return _done(
        facts,
        md,
        blocks,
        f"Biznes o'zi {uz.speech_amount(c.operating)} ishlab chiqardi.",
        f"Kassa {M(c.closing)}: biznesdan +{M(c.operating)}",
    )


def net_position_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    n = cfo.net_position(s, args.get("month"))
    recv = ", ".join(f"{k} {M(v)}" for k, v in n.receivables) or "yo'q"
    pay = ", ".join(f"{k} {M(v)}" for k, v in n.payables) or "yo'q"
    md = (
        f"Kassa **{M(n.cash)}**. Sizga qarzdorlar: {recv}. Siz qarzdorsiz: {pay}; kredit qoldig'i **{M(n.loan)}**. "
        f"Sof pozitsiya (kassa + debitorlar − kreditorlar − kredit): **{M(n.net_cash)}**. "
        f"Kassa doimiy majburiy to'lovlarning (oyiga ~{M(n.fixed_monthly)}) **{str(n.months_covered.quantize(Decimal('0.1'))).replace('.', ',')}** oyini qoplaydi."
    )
    items = [{"label": "Kassa", "value": M(n.cash), "tone": "muted"}]
    items += [
        {"label": f"{k} (bizga qarz)", "value": M(v), "tone": "success"} for k, v in n.receivables
    ]
    items += [{"label": f"{k} (biz qarzmiz)", "value": M(v), "tone": "warn"} for k, v in n.payables]
    items += [
        {"label": "Kredit qoldig'i", "value": M(n.loan), "tone": "warn"},
        {"label": "Sof pozitsiya", "value": M(n.net_cash), "tone": "muted"},
    ]
    blocks = [
        {
            "type": "metric_grid",
            "id": "net_position",
            "title": f"Sof pozitsiya · {month_name(n.month)}",
            "caption": "Kassadan qarzlarni ayirgandan keyin aslida qancha pul qoladi.",
            "items": items,
        }
    ]
    facts = {
        "cash": M(n.cash),
        "receivables": {k: M(v) for k, v in n.receivables},
        "payables": {k: M(v) for k, v in n.payables},
        "loan": M(n.loan),
        "net_cash": M(n.net_cash),
        "fixed_monthly": M(n.fixed_monthly),
        "months_covered": str(n.months_covered.quantize(Decimal("0.1"))).replace(".", ","),
    }
    return _done(
        facts,
        md,
        blocks,
        f"Sof pozitsiya {uz.speech_amount(n.net_cash)}.",
        f"Sof pozitsiya {M(n.net_cash)}",
    )


STATUS_UZ = {"good": "Yaxshi", "problem": "Muammoli", "watch": "Kuzatish kerak"}


def kpi_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    sc = cfo.kpi_scorecard(s, args.get("month"))
    rows = []
    for k in sc.kpis:
        v = P(k.value) if k.key not in ("cash",) else M(k.value)
        t = P(k.target) if k.target else "—"
        extra = f" (oyiga ~{M(k.gap_money)} ortiqcha)" if k.gap_money else ""
        rows.append(f"| {k.label} | {v} | {t} | {STATUS_UZ[k.status]}{extra} |")
    md = (
        f"**Yakuniy baho ({month_name(sc.month)}): {sc.overall}.**\n\n| Ko'rsatkich | Qiymat | Maqsad | Holat |\n|---|---|---|---|\n"
        + "\n".join(rows)
    )
    blocks = [
        {
            "type": "metric_grid",
            "id": "kpi",
            "title": f"KPI · {month_name(sc.month)}",
            "caption": "Qizil — maqsaddan yomon, yashil — me'yorda.",
            "items": [
                {
                    "label": k.label,
                    "value": P(k.value) if k.key != "cash" else M(k.value),
                    "note": (f"maqsad {P(k.target)}" if k.target else "")
                    + (f", +{M(k.gap_money)}/oy" if k.gap_money else ""),
                    "tone": {"good": "success", "problem": "danger", "watch": "warn"}[k.status],
                }
                for k in sc.kpis
            ],
        }
    ]
    facts = {
        "overall": sc.overall,
        "kpis": {
            k.key: {
                "value": P(k.value) if k.key != "cash" else M(k.value),
                "target": P(k.target) if k.target else None,
                "status": STATUS_UZ[k.status],
                "gap_money": M(k.gap_money) if k.gap_money else None,
            }
            for k in sc.kpis
        },
    }
    return _done(facts, md, blocks, f"Yakuniy baho: {sc.overall}.", f"Yakuniy baho: {sc.overall}")


def plan_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    pv = cfo.plan_vs_actual(s, args.get("month"))

    def fmt(x: Decimal, unit: str) -> str:
        return (
            f"{x.quantize(Decimal(1)):,}".replace(",", " ")
            if unit == "count"
            else (uz.format_som(x.quantize(Decimal(1))) if abs(x) < 1_000_000 else M(x))
        )

    rows = "\n".join(
        f"| {x.label} | {fmt(x.plan, x.unit)} | {fmt(x.fact, x.unit)} | {('+' if x.diff_pct >= 0 else '')}{P(x.diff_pct)} | {'✓' if x.favourable else '✗'} |"
        for x in pv.lines
    )
    worst = (
        "; ".join(
            f"{x.label}: {fmt(x.fact, x.unit)} (reja {fmt(x.plan, x.unit)})" for x in pv.worst
        )
        or "yo'q"
    )
    md = (
        f"**Reja va fakt ({month_name(pv.month)})**\n\n| Ko'rsatkich | Reja | Fakt | Farq | |\n|---|---|---|---|---|\n{rows}\n\n"
        f"Eng katta salbiy farqlar: {worst}. Yil boshidan cheklar rejadan **{P(pv.ytd_checks_pct)}**."
    )
    facts = {
        "month": pv.month,
        "lines": {
            x.key: {
                "plan": fmt(x.plan, x.unit),
                "fact": fmt(x.fact, x.unit),
                "diff_pct": P(x.diff_pct),
            }
            for x in pv.lines
        },
        "worst": [x.label for x in pv.worst],
        "ytd_checks_pct": P(pv.ytd_checks_pct),
    }
    blocks = [
        {
            "type": "scenario_table",
            "id": "plan_fact",
            "title": f"Reja-fakt · {month_name(pv.month)}",
            "caption": "✗ — rejadan yomon. Eng katta pul farqlariga qarang.",
            "columns": ["Reja", "Fakt", "Farq"],
            "rows": [
                {
                    "label": x.label,
                    "values": [fmt(x.plan, x.unit), fmt(x.fact, x.unit), P(x.diff_pct)],
                }
                for x in pv.lines
            ],
        }
    ]
    return _done(
        facts,
        md,
        blocks,
        "Reja va fakt solishtirildi.",
        f"Reja-fakt: tushum {P(next(x.diff_pct for x in pv.lines if x.key == 'sof tushum'))}",
    )


def drivers_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    d = cfo.driver_decomposition(s, args.get("month"))
    wd = ", ".join(f"{WD[w]} {n.quantize(Decimal(1))}" for w, n in d.weekday_checks)
    ch = ", ".join(
        f"{name} {M(r)} (komissiyadan keyin {M(net)})" for name, r, net in d.channels if r
    )
    md = (
        f"Tushum = cheklar × o'rtacha chek. {month_name(d.month).capitalize()}: **{d.checks.quantize(Decimal(1))} chek × {uz.format_som(d.avg_check.quantize(Decimal(1)))}** = **{M(d.revenue)}** "
        f"(o'tgan oy {d.prev_checks.quantize(Decimal(1))} × {uz.format_som(d.prev_avg_check.quantize(Decimal(1)))} = {M(d.prev_revenue)}). "
        f"O'zgarish: cheklar soni hisobiga **{('+' if d.effect_checks >= 0 else '')}{M(d.effect_checks)}**, o'rtacha chek hisobiga **{('+' if d.effect_avg_check >= 0 else '')}{M(d.effect_avg_check)}**. "
        f"Hafta kunlari bo'yicha o'rtacha cheklar: {wd}. Kanallar: {ch}."
    )
    facts = {
        "month": d.month,
        "revenue": M(d.revenue),
        "prev_revenue": M(d.prev_revenue),
        "checks": str(d.checks.quantize(Decimal(1))),
        "prev_checks": str(d.prev_checks.quantize(Decimal(1))),
        "avg_check": uz.format_som(d.avg_check.quantize(Decimal(1))),
        "effect_checks": M(d.effect_checks),
        "effect_avg_check": M(d.effect_avg_check),
        "weekday_checks": {WD[w]: str(n.quantize(Decimal(1))) for w, n in d.weekday_checks},
    }
    return _done(
        facts,
        md,
        [],
        "Tushum o'zgarishi cheklar va o'rtacha chekka ajratildi.",
        f"Tushum {M(d.revenue)}",
    )


def debt_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    s = summary_of(ctx)
    if not s:
        return no_reports()
    ds = cfo.debt_schedule(s)
    n = cfo.net_position(s)
    if ds is None:
        text = "Jadvalda bank krediti topilmadi."
        return envelope(
            ok=True,
            md=text,
            say=text,
            answer={"verdict": "info", "headline": text, "reason": "", "steps": []},
        )
    pay = ", ".join(f"{k} {M(v)}" for k, v in n.payables) or "yo'q"
    md = (
        f"Bank krediti qoldig'i **{M(ds.balance)}** (yiliga {str(ds.rate_pct).replace('.', ',')}%), oyiga **{M(ds.principal_monthly)}** asosiy qarz + foiz. "
        f"Shu tartibda **{ds.months_left} oyda**, {month_name(ds.payoff_month)}da yopiladi; qolgan foiz jami ~**{M(ds.remaining_interest)}**. "
        f"Muddatidan oldin hozir yopsangiz shu foizni tejaysiz (bankda jarima bormi — aniqlang). Boshqa majburiyatlar: {pay}."
    )
    rows = [
        {
            "when": month_name(m),
            "action": f"Kredit: asosiy {M(p)} + foiz {M(i)}",
            "amount": f"qoldiq {M(b)}",
        }
        for m, p, i, b in ds.rows[:6]
    ]
    blocks = [
        {
            "type": "plan_timeline",
            "id": "debt",
            "title": "Kredit jadvali (keyingi oylar)",
            "caption": "Har oy qancha to'lanadi va qoldiq qanday kamayadi.",
            "steps": rows,
        }
    ]
    facts = {
        "balance": M(ds.balance),
        "rate_pct": str(ds.rate_pct),
        "principal_monthly": M(ds.principal_monthly),
        "months_left": ds.months_left,
        "payoff": month_name(ds.payoff_month),
        "remaining_interest": M(ds.remaining_interest),
        "payables": {k: M(v) for k, v in n.payables},
    }
    return _done(
        facts,
        md,
        blocks,
        f"Kredit {ds.months_left} oyda yopiladi.",
        f"Kredit {month_name(ds.payoff_month)}da yopiladi",
    )


MONTH = {"type": "string", "format": "date"}
CFO_TOOLS: list[Tool] = [
    Tool(
        "break_even",
        "Zararsizlik nuqtasi: marja, doimiy xarajat, kuniga nechta chek kerak (kredit bilan va kreditsiz), hozirgi cheklar.",
        {"type": "object", "properties": {"month": MONTH}},
        break_even_tool,
    ),
    Tool(
        "stress_test",
        "Savdo 10/20/30/40% tushsa oylik pul natijasi va maksimal chidash mumkin bo'lgan tushish.",
        {
            "type": "object",
            "properties": {
                "drops": {"type": "array", "items": {"type": "integer"}},
                "month": MONTH,
            },
        },
        stress_tool,
    ),
    Tool(
        "cash_sources",
        "Kassadagi pul qayerdan: operatsion, investitsiya, moliyaviy (ta'sischi, kredit, qaytarish, foiz, dividend).",
        {"type": "object", "properties": {}},
        cash_sources_tool,
    ),
    Tool(
        "net_position",
        "Sof pozitsiya: kassa, debitorlar (agregatorlar), kreditorlar (yetkazib beruvchi, soliq), kredit qoldig'i, necha oy qoplaydi.",
        {"type": "object", "properties": {"month": MONTH}},
        net_position_tool,
    ),
    Tool(
        "kpi_scorecard",
        "KPI: food cost, labor, prime, ijara, EBITDA, sof marja, pul oqimi, mijozlar oqimi — maqsadga nisbatan baho.",
        {"type": "object", "properties": {"month": MONTH}},
        kpi_tool,
    ),
    Tool(
        "plan_vs_actual",
        "Reja va fakt: har bir qator, eng katta salbiy farqlar, yil boshidan cheklar.",
        {"type": "object", "properties": {"month": MONTH}},
        plan_tool,
    ),
    Tool(
        "driver_decomposition",
        "Tushum omillari: cheklar × o'rtacha chek, o'tgan oyga nisbatan ta'sir, hafta kunlari, kanallar.",
        {"type": "object", "properties": {"month": MONTH}},
        drivers_tool,
    ),
    Tool(
        "debt_schedule",
        "Kredit jadvali: qoldiq, oylik to'lov, qachon yopiladi, qolgan foiz, muddatidan oldin yopish samarasi.",
        {"type": "object", "properties": {}},
        debt_tool,
    ),
]


def trend_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    from apps.insights.trends import as_dict, find_trends

    found = [as_dict(t) for t in find_trends(ctx.cached.result.today)]
    if not found:
        text = "Oxirgi haftalarda savdo, xarajat ulushi va sof pulda 3 hafta ketma-ket yomonlashish yo'q."
        return envelope(
            ok=True,
            facts={"trends": []},
            md=text,
            say=text,
            answer={
                "verdict": "info",
                "headline": "Xavfli trend yo'q",
                "reason": text,
                "steps": [],
            },
        )
    md = "\n".join(f"- {t['text']}" for t in found)
    return _done({"trends": found}, md, [], found[0]["text"], f"{len(found)} ta salbiy trend")


CFO_TOOLS.append(
    Tool(
        "trend_watch",
        "Haftalik trendlar: savdo, xarajat ulushi, sof pul 3+ hafta ketma-ket yomonlashganmi.",
        {"type": "object", "properties": {}},
        trend_tool,
    )
)

TOOLS.update({t.name: t for t in CFO_TOOLS})

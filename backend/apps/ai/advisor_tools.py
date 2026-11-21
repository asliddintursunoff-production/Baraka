"""Advisor tools: deterministic engine answers (apps/engine/advisor.py) as tool envelopes.

Each returns facts, display, say, ui_blocks, assumptions and a template answer with a
dated plan. Inputs that are not data come back as editable `assumptions` (the chat
re-runs the same tool with a changed value, no LLM). Missing key inputs produce `needs`
(one precise question + a data-based default chip) instead of a guessed number.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from apps.engine import advisor as A
from apps.engine.types import EngineError
from apps.finance.models import Debt, Transaction

from . import uz_format as uz
from .tools import Tool, ToolArgError, ToolContext, envelope, insufficient, money, propose

WD = uz.WEEKDAYS


CATEGORY_UZ = {
    "payroll": "ish haqi",
    "loan": "kredit",
    "rent": "ijara",
    "tax": "soliq",
    "supplier": "ta'minotchi",
    "kommunal": "kommunal",
}
FIXED = set(CATEGORY_UZ)


def M(x: Decimal) -> str:
    """Millions for big amounts, plain so'm under 1 mln (an average check is 35 000 so'm)."""
    return uz.format_mln(x) if abs(x) >= 1_000_000 else uz.format_som(x)


def P(x: Decimal) -> str:
    return str(x).replace(".", ",")


def Dt(d: date) -> str:
    return uz.format_date(d)


def _assumptions(tool: str, args: dict[str, Any], items: Any) -> list[dict[str, Any]]:
    out = []
    for a in items:
        out.append(
            {
                "text": a.text,
                "editable": a.editable,
                "key": a.key,
                "value": a.value,
                "tool": tool,
                "args": {
                    k: (str(v) if isinstance(v, (Decimal, date)) else v) for k, v in args.items()
                },
            }
        )
    return out


def _needs(tool: str, args: dict[str, Any], questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Missing inputs: ask, never guess. A data-based default is offered as an editable chip."""
    lines = [f"{q['text']} ({q['why']})" for q in questions]
    return envelope(
        ok=True,
        needs=questions,
        say=questions[0]["text"],
        assumptions=[
            {
                "text": f"Taxmin: {q['default_text']} — to'g'rimi?",
                "editable": True,
                "key": q["key"],
                "value": q["default"],
                "tool": tool,
                "args": args,
            }
            for q in questions
            if q.get("default") is not None
        ],
        answer={
            "verdict": "info",
            "headline": "Buni aniq hisoblash uchun quyidagilar kerak:",
            "reason": " ".join(lines),
            "steps": [],
        },
    )


def _plan_block(bid: str, title: str, steps: list[dict[str, str]]) -> dict[str, Any]:
    return {"type": "plan_timeline", "id": bid, "title": title, "steps": steps}


def _answer(headline: str, reason: str, plan: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "verdict": "info",
        "headline": headline,
        "reason": reason,
        "steps": [
            f"{p['when']}: {p['action']}" + (f" ({p['amount']})" if p.get("amount") else "")
            for p in plan
        ][:3],
        "plan": plan,
    }


def _base(ctx: ToolContext) -> Any:
    if ctx.short_history:
        return None
    return A.advisor_base(ctx.cached.inp)


# --- business_snapshot --------------------------------------------------------------------
def business_snapshot_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    today = base.today
    this_m = today.replace(day=1)
    last_m = (this_m - timedelta(days=1)).replace(day=1)
    prev_m = (last_m - timedelta(days=1)).replace(day=1)
    rows = (
        Transaction.objects.filter(is_actual=True, txn_date__gte=prev_m, txn_date__lt=this_m)
        .annotate(m=TruncMonth("txn_date"))
        .values("m", "direction", "category")
        .annotate(s=Sum("amount"))
    )
    cats: dict[date, dict[str, Decimal]] = {last_m: {}, prev_m: {}}
    rev: dict[date, Decimal] = {last_m: Decimal(0), prev_m: Decimal(0)}
    for r in rows:
        m = r["m"].date() if hasattr(r["m"], "date") else r["m"]
        if r["direction"] == "in":
            rev[m] = rev.get(m, Decimal(0)) + r["s"]
        else:
            cat = r["category"] or "boshqa"
            cats.setdefault(m, {})[cat] = cats.get(m, {}).get(cat, Decimal(0)) + r["s"]
    debts = Debt.objects.filter(status__in=[Debt.Status.OPEN, Debt.Status.PENDING]).aggregate(
        s=Sum("amount")
    )["s"] or Decimal(0)
    s = A.business_snapshot(
        base,
        month_categories=cats.get(last_m, {}),
        prev_month_categories=cats.get(prev_m, {}),
        revenue_month=rev.get(last_m),
        revenue_prev_month=rev.get(prev_m),
        debts_total=debts,
    )

    def flag_text(f: A.Flag) -> str:
        if f.text == "Eng kuchli kun":
            return f"Eng kuchli kun — {WD[int(f.value)]} ({M(s.weekday_revenue[int(f.value)])}/kun)"
        if f.text.startswith("Kassa"):
            return f"{f.text}: eng past {M(Decimal(f.value))} ({Dt(s.lowest_date)})"
        if f.text.startswith('"'):
            return f'"{CATEGORY_UZ.get(f.text.split(chr(34))[1], f.text.split(chr(34))[1])}" xarajati o\'sgan: {P(Decimal(f.value.strip("+%")))}%'
        return f"{f.text}: {P(Decimal(f.value.strip('+%'))) if f.value.strip('+%').replace('.', '').replace('-', '').isdigit() else f.value}{'%' if f.value.endswith('%') else ''}"

    strengths = [flag_text(f) for f in s.strengths]
    weaknesses = [flag_text(f) for f in s.weaknesses]
    if any(f.text.startswith("Eng zaif") for f in s.weaknesses):
        weaknesses = [
            w
            if not w.startswith("Eng zaif")
            else f"{WD[s.weakest_day].capitalize()} savdosi {M(s.weekday_revenue[s.weakest_day])}/kun — "
            f"{WD[s.strongest_day]}dan {next(f.value for f in s.weaknesses if f.text.startswith('Eng zaif'))} past"
            for w in weaknesses
        ]
    cat_items = [
        {
            "label": CATEGORY_UZ.get(c, c),
            "value": M(v),
            "note": (f"o'tgan oyga {('+' if m > 0 else '')}{m}%" if m is not None else ""),
            "tone": "warn" if m is not None and m >= 10 else "muted",
        }
        for c, v, m in s.top_categories
    ]
    blocks = [
        {
            "type": "metric_grid",
            "id": "snapshot",
            "title": "Biznesingiz qisqacha",
            "items": [
                {
                    "label": "Oylik savdo (o'rtacha)",
                    "value": M(s.avg_month_revenue),
                    "note": f"kuniga {M(s.avg_day_revenue)}",
                    "tone": "muted",
                },
                {
                    "label": "Yalpi marja",
                    "value": f"{P(s.gross_margin_pct)}%",
                    "note": f"xarajat ulushi {P(100 - s.gross_margin_pct)}%",
                    "tone": "success" if s.gross_margin_pct >= 50 else "warn",
                },
                {
                    "label": "Eng qiyin kun",
                    "value": Dt(s.lowest_date),
                    "note": f"kassada {M(s.lowest)}",
                    "tone": "warn" if s.lowest < base.safe_min * 2 else "muted",
                },
                {
                    "label": "Energiya (o'tgan oy)",
                    "value": M(s.energy_month),
                    "note": "gaz, svet, kommunal",
                    "tone": "muted",
                },
                {
                    "label": "Qarzlar",
                    "value": M(s.debts_total),
                    "note": "siz aytgan qarzlar",
                    "tone": "muted",
                },
                {
                    "label": "Zaif kun",
                    "value": WD[s.weakest_day],
                    "note": f"{M(s.weekday_revenue[s.weakest_day])}/kun",
                    "tone": "warn",
                },
            ],
        },
        {
            "type": "metric_grid",
            "id": "flags",
            "title": "Kuchli va zaif tomonlar",
            "items": [
                *({"label": "Kuchli", "value": t, "tone": "success"} for t in strengths),
                *({"label": "Zaif", "value": t, "tone": "warn"} for t in weaknesses),
            ],
        },
    ]
    if cat_items:
        blocks.append(
            {
                "type": "metric_grid",
                "id": "top_categories",
                "title": "Eng katta 5 xarajat (o'tgan oy)",
                "items": cat_items,
            }
        )
    plan = [
        {
            "when": f"{WD[s.weakest_day]} kunlari",
            "action": f"{WD[s.weakest_day].capitalize()} savdosini {WD[s.strongest_day]} darajasiga yaqinlashtirish",
            "amount": M(s.weekday_revenue[s.strongest_day] - s.weekday_revenue[s.weakest_day]),
        }
    ]
    variable = [(c, v) for c, v, _ in s.top_categories if c not in FIXED]
    if variable:
        c, v = variable[0]
        plan.append(
            {
                "when": "Keyingi oy",
                "action": f"\"{c}\" xaridini ta'minotchi bilan qayta kelishish (eng katta o'zgaruvchan xarajat)",
                "amount": M(v),
            }
        )
    plan.append(
        {
            "when": Dt(s.lowest_date),
            "action": "Eng qiyin kun: shu kungacha katta xarajat qilmaslik",
            "amount": M(s.lowest),
        }
    )
    headline = f"Oylik savdo {M(s.avg_month_revenue)}, marja {P(s.gross_margin_pct)}%, eng qiyin kun {Dt(s.lowest_date)}"
    return envelope(
        facts={
            "avg_month_revenue": money(s.avg_month_revenue),
            "avg_day_revenue": money(s.avg_day_revenue),
            "gross_margin_pct": str(s.gross_margin_pct),
            "lowest": money(s.lowest),
            "lowest_date": s.lowest_date.isoformat(),
            "energy_month": money(s.energy_month),
            "debts_total": money(s.debts_total),
            "weekday_revenue": {WD[i]: money(v) for i, v in enumerate(s.weekday_revenue)},
            "top_categories": [
                {"category": c, "amount": money(v), "mom_pct": str(m) if m is not None else None}
                for c, v, m in s.top_categories
            ],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "revenue_mom_pct": str(s.revenue_mom_pct) if s.revenue_mom_pct is not None else None,
        },
        display={"headline": headline},
        say=f"Oylik savdo {uz.speech_amount(s.avg_month_revenue)}, marja {s.gross_margin_pct} foiz. Eng qiyin kun {uz.uz_ordinal_date(s.lowest_date)}.",
        ui_blocks=blocks,
        assumptions=[],
        answer=_answer(
            headline,
            "Kuchli: " + "; ".join(strengths) + ". Zaif: " + "; ".join(weaknesses) + ".",
            plan,
        ),
    )


# --- when_can_afford / savings_goal -------------------------------------------------------
def _afford_rows(rs: list[tuple[str, A.AffordResult]]) -> list[dict[str, Any]]:
    return [
        {
            "label": "Eng erta xavfsiz sana",
            "values": [Dt(r.earliest) if r.earliest else "180 kunda yo'q" for _, r in rs],
        },
        {
            "label": "O'shanda eng past qoldiq",
            "values": [M(r.lowest_after) if r.lowest_after is not None else "—" for _, r in rs],
        },
    ]


def when_can_afford_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    amount = Decimal(args["amount"])
    mode = args.get("mode", "cash")
    inp = ctx.cached.inp
    try:
        r = A.when_can_afford(
            inp,
            amount,
            mode=mode,
            n=args.get("n"),
            rate=args.get("rate"),
            months=args.get("months"),
            target=args.get("target_date"),
            base=base,
        )
        alts = [("Naqd" if mode == "cash" else "Tanlangan", r)]
        if mode == "cash":
            alts.append(
                (
                    "6 oyga bo'lib",
                    A.when_can_afford(inp, amount, mode="installments", n=6, base=base),
                )
            )
            if args.get("rate"):
                alts.append(
                    (
                        f"Kredit {args['rate']}%",
                        A.when_can_afford(
                            inp,
                            amount,
                            mode="loan",
                            rate=args["rate"],
                            months=int(args.get("months") or 12),
                            base=base,
                        ),
                    )
                )
    except EngineError as exc:
        raise ToolArgError(str(exc)) from exc
    plan: list[dict[str, str]] = []
    if r.earliest:
        headline = f"{M(amount)} ni eng erta {Dt(r.earliest)} da olsangiz xavfsiz"
        if r.earliest > base.today:
            plan.append(
                {
                    "when": f"{Dt(r.earliest)} gacha",
                    "action": "Bu xaridni qilmang, kassani xavfsiz chegaradan yuqori saqlang",
                    "amount": M(r.capacity_now),
                }
            )
        plan.append({"when": Dt(r.earliest), "action": "Xaridni qiling", "amount": M(amount)})
        if r.earlier_with_revenue_10 and r.earlier_with_revenue_10 < r.earliest:
            plan.append(
                {
                    "when": f"{Dt(r.earlier_with_revenue_10)} (savdo +10% bo'lsa)",
                    "action": "Savdo 10% oshsa xarid ertaroq bo'ladi",
                    "amount": M(amount),
                }
            )
        reason = f"Hozir xavfsiz sarflash mumkin bo'lgan summa: {M(r.capacity_now)}. {Dt(r.earliest)} da olsangiz kassada eng kami {M(r.lowest_after or Decimal(0))} qoladi."
    else:
        headline = f"{M(amount)} ga 180 kun ichida xavfsiz sana yo'q"
        plan.append(
            {
                "when": f"{Dt(base.today)} dan har oy",
                "action": "Alohida jamg'arib boring",
                "amount": M(r.monthly_set_aside),
            }
        )
        if r.revenue_pct_needed is not None:
            plan.append(
                {
                    "when": f"{Dt(r.target)} gacha",
                    "action": f"Savdoni {r.revenue_pct_needed}% oshiring — shunda xarid mumkin bo'ladi",
                }
            )
        plan.append(
            {
                "when": f"{Dt(r.target)} gacha",
                "action": "Yoki xarajatni oyiga shuncha qisqartiring",
                "amount": M(r.monthly_set_aside),
            }
        )
        reason = f"{Dt(r.target)} ga yetishmaydigan summa: {M(r.shortfall)}."
    alt_names = [n for n, _ in alts]
    blocks = [
        _plan_block("afford_plan", "Reja", [{**p, "tone": "info"} for p in plan]),
        {
            "type": "scenario_table",
            "id": "afford_options",
            "title": f"{M(amount)}: to'lash usullari",
            "columns": alt_names,
            "rows": _afford_rows(alts),
            "highlight": 0,
        },
    ]
    facts = {
        "amount": money(amount),
        "earliest": r.earliest.isoformat() if r.earliest else None,
        "lowest_after": money(r.lowest_after) if r.lowest_after is not None else None,
        "capacity_now": money(r.capacity_now),
        "shortfall": money(r.shortfall),
        "monthly_set_aside": money(r.monthly_set_aside),
        "revenue_pct_needed": str(r.revenue_pct_needed)
        if r.revenue_pct_needed is not None
        else None,
        "earlier_with_revenue_10": r.earlier_with_revenue_10.isoformat()
        if r.earlier_with_revenue_10
        else None,
        "alternatives": {n: (x.earliest.isoformat() if x.earliest else None) for n, x in alts},
    }
    return envelope(
        facts=facts,
        display={
            "amount": M(amount),
            "earliest": Dt(r.earliest) if r.earliest else "",
            "capacity_now": M(r.capacity_now),
            "monthly_set_aside": M(r.monthly_set_aside),
            "alternatives": {n: (Dt(x.earliest) if x.earliest else "yo'q") for n, x in alts},
        },
        say=(
            f"Eng erta xavfsiz sana {uz.uz_ordinal_date(r.earliest)}."
            if r.earliest
            else f"180 kun ichida xavfsiz sana yo'q. Har oy {uz.speech_amount(r.monthly_set_aside)} jamg'aring."
        ),
        ui_blocks=blocks,
        assumptions=_assumptions("when_can_afford", args, r.assumptions),
        answer=_answer(headline, reason, plan),
    )


def savings_goal_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    amount = Decimal(args["amount"])
    by = args.get("by_date")
    r = A.savings_goal(ctx.cached.inp, amount, by, base=base)
    plan: list[dict[str, str]] = []
    if r.earliest:
        headline = f"{M(amount)} ni {Dt(r.earliest)} da ajratib qo'ya olasiz"
        plan.append(
            {
                "when": f"{Dt(base.today)} – {Dt(r.earliest)}",
                "action": "Bu summaga tegmang, majburiy to'lovlardan keyin yig'ilib boradi",
                "amount": M(amount),
            }
        )
        if r.earlier_with_revenue_10 and r.earlier_with_revenue_10 < r.earliest:
            plan.append(
                {
                    "when": Dt(r.earlier_with_revenue_10),
                    "action": "Savdo 10% oshsa, shu sanaga yetadi",
                    "amount": M(amount),
                }
            )
    else:
        headline = f"{M(amount)} 180 kun ichida yig'ilmaydi"
    if by and (not r.earliest or r.earliest > by):
        plan.append(
            {
                "when": f"{Dt(base.today)} dan har oy",
                "action": f"{Dt(by)} ga yetish uchun qo'shimcha jamg'aring yoki xarajatni qisqartiring",
                "amount": M(r.monthly_set_aside),
            }
        )
        if r.revenue_pct_needed is not None:
            plan.append(
                {
                    "when": f"{Dt(by)} gacha",
                    "action": f"Yoki savdoni {r.revenue_pct_needed}% oshiring",
                }
            )
    reason = (
        f"Hozir xavfsiz ajratish mumkin: {M(r.capacity_now)}. Majburiy to'lovlar hisobga olingan."
    )
    return envelope(
        facts={
            "amount": money(amount),
            "earliest": r.earliest.isoformat() if r.earliest else None,
            "capacity_now": money(r.capacity_now),
            "monthly_set_aside": money(r.monthly_set_aside),
            "revenue_pct_needed": str(r.revenue_pct_needed)
            if r.revenue_pct_needed is not None
            else None,
            "earlier_with_revenue_10": r.earlier_with_revenue_10.isoformat()
            if r.earlier_with_revenue_10
            else None,
        },
        display={
            "earliest": Dt(r.earliest) if r.earliest else "",
            "capacity_now": M(r.capacity_now),
            "monthly_set_aside": M(r.monthly_set_aside),
        },
        say=(
            f"{uz.speech_amount(amount)} {uz.uz_ordinal_date(r.earliest)} da yig'iladi."
            if r.earliest
            else "180 kun ichida yig'ilmaydi."
        ),
        ui_blocks=[_plan_block("savings_plan", "Jamg'arma rejasi", plan)],
        assumptions=[
            {
                "text": "Muddat (sana)",
                "editable": True,
                "key": "by_date",
                "value": by.isoformat() if by else "",
                "tool": "savings_goal",
                "args": {k: str(v) for k, v in args.items()},
            }
        ],
        answer=_answer(headline, reason, plan),
    )


# --- debts --------------------------------------------------------------------------------
def _find_debt(name: str | None) -> Debt | None:
    from apps.ingestion.normalize import name_key

    qs = Debt.objects.exclude(status=Debt.Status.PAID).order_by("-created_at")
    if not name:
        return qs.first()
    key = name_key(name)
    return next(
        (
            d
            for d in qs
            if key and (key in name_key(d.counterparty) or name_key(d.counterparty) in key)
        ),
        None,
    )


def _debt_compare(
    ctx: ToolContext, debt: Debt, n: int, args: dict[str, Any], pending_plan: dict[str, Any] | None
) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    r = A.debt_payoff(ctx.cached.inp, Decimal(debt.amount), debt.due_date, n=n, base=base)
    names = {"now": "Hozir", "split": f"{n} oyga bo'lib", "on_due": "Muddatida"}
    by = {o.kind: o for o in r.options}
    rec = by[r.recommended]
    rows = [
        {
            "label": "To'lov sanasi",
            "values": [", ".join(Dt(d) for d, _ in o.schedule[:3]) for o in r.options],
        },
        {"label": "Eng past qoldiq", "values": [M(o.lowest) for o in r.options]},
        {"label": "Qachon", "values": [Dt(o.lowest_date) for o in r.options]},
        {"label": "Xavfsizmi?", "values": ["ha" if o.safe else "yo'q" for o in r.options]},
    ]
    plan = [
        {"when": Dt(d), "action": f"{debt.counterparty}ga to'lang", "amount": M(a)}
        for d, a in rec.schedule[:6]
    ]
    safe_txt = "xavfsiz" if rec.safe else "eng kam zararli (hech biri to'liq xavfsiz emas)"
    headline = f"{debt.counterparty}: {names[r.recommended].lower()} to'lash — {safe_txt}"
    reason = (
        f"Hozir to'lasangiz kassa {Dt(by['now'].lowest_date)} da {M(by['now'].lowest)} gacha tushadi; "
        f"{names[r.recommended].lower()} to'lasangiz eng kami {M(rec.lowest)} ({Dt(rec.lowest_date)})."
    )
    blocks = [
        {
            "type": "debt_list",
            "id": "debts",
            "title": "Qarzlar",
            "items": [
                {
                    "counterparty": debt.counterparty,
                    "amount": M(debt.amount),
                    "due": Dt(debt.due_date) if debt.due_date else "muddat yo'q",
                    "note": debt.terms_text
                    or ("tasdiq kutilmoqda" if debt.status == Debt.Status.PENDING else ""),
                    "tone": "warn",
                }
            ],
            "total": M(debt.amount),
        },
        {
            "type": "scenario_table",
            "id": "debt_options",
            "title": "Qarzni qanday to'lash",
            "columns": [names[o.kind] for o in r.options],
            "rows": rows,
            "highlight": [o.kind for o in r.options].index(r.recommended),
        },
        _plan_block("debt_plan", "Tavsiya etilgan reja", plan),
    ]
    return envelope(
        facts={
            "debt": {
                "counterparty": debt.counterparty,
                "amount": money(debt.amount),
                "due_date": debt.due_date.isoformat() if debt.due_date else None,
            },
            "options": {
                o.kind: {
                    "lowest": money(o.lowest),
                    "lowest_date": o.lowest_date.isoformat(),
                    "safe": o.safe,
                    "schedule": [
                        {"date": d.isoformat(), "amount": money(a)} for d, a in o.schedule
                    ],
                }
                for o in r.options
            },
            "recommended": r.recommended,
        },
        display={
            "options": {
                names[o.kind]: {"lowest": M(o.lowest), "date": Dt(o.lowest_date)} for o in r.options
            }
        },
        say=f"{names[r.recommended]} to'lash tavsiya etiladi: kassada eng kami {uz.speech_amount(rec.lowest)} qoladi.",
        ui_blocks=blocks,
        assumptions=_assumptions(
            "debt_payoff", {**args, "counterparty": debt.counterparty}, r.assumptions
        ),
        proposed_plan=pending_plan,
        answer=_answer(headline, reason, plan),
    )


def record_debt_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    """'Shavkat akaga 30 mln qarzim bor' -> a pending Debt + approval card, then the comparison."""
    from apps.ingestion.normalize import clean_name

    name = clean_name(args["counterparty"])[:120] or "Noma'lum"
    debt = Debt.objects.create(
        business=ctx.business,
        counterparty=name,
        amount=Decimal(args["amount"]),
        due_date=args.get("due_date"),
        terms_text=str(args.get("note") or "")[:300],
    )
    summary = f"Qarz: {name} — {M(debt.amount)}" + (
        f", muddat {Dt(debt.due_date)}" if debt.due_date else ""
    )
    plan = propose(ctx, "record_debt", {"debt_id": debt.pk, "summary": summary}, None)
    return _debt_compare(ctx, debt, int(args.get("n") or 3), {"counterparty": name}, plan)


def debt_payoff_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    debt = _find_debt(args.get("counterparty"))
    if debt is None and args.get("amount"):
        return record_debt_tool(
            ctx,
            {
                "counterparty": args.get("counterparty") or "Qarz",
                "amount": args["amount"],
                "due_date": args.get("due_date"),
                "n": args.get("n"),
            },
        )
    if debt is None:
        return _needs(
            "debt_payoff",
            args,
            [
                {
                    "key": "amount",
                    "text": "Qarz qancha va kimga?",
                    "why": "to'lash variantlarini hisoblash uchun",
                    "default": None,
                }
            ],
        )
    if args.get("due_date"):
        debt.due_date = args["due_date"]
        debt.save(update_fields=["due_date"])
    return _debt_compare(ctx, debt, int(args.get("n") or 3), args, None)


# --- loans --------------------------------------------------------------------------------
def loan_affordability_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    if args.get("rate") is None:
        return _needs(
            "loan_affordability",
            args,
            [
                {
                    "key": "rate",
                    "text": "Bank yillik necha foizda kredit beradi?",
                    "why": "oylik to'lovni annuitet formulasi bilan hisoblash uchun",
                    "default": None,
                }
            ],
        )
    months = int(args.get("months") or 12)
    amount = Decimal(args["amount"]) if args.get("amount") else None
    r = A.loan_affordability(ctx.cached.inp, Decimal(args["rate"]), months, amount, base=base)
    plan = []
    if amount and r.payment:
        ok = amount <= r.max_safe_amount
        headline = f"{M(amount)} kredit: oyiga {M(r.payment)} — " + (
            "yopa olasiz" if ok else "xavfli"
        )
        plan.append(
            {
                "when": f"{Dt(base.today)} dan {months} oy",
                "action": "Har oy kredit to'lovi",
                "amount": M(r.payment),
            }
        )
    else:
        headline = f"Xavfsiz kredit: {M(r.max_safe_amount)} gacha ({months} oy, {r.rate}%)"
    plan.append(
        {
            "when": "Kredit olishdan oldin",
            "action": f"Summani {M(r.max_safe_amount)} dan oshirmang",
            "amount": M(r.max_safe_payment) + "/oy",
        }
    )
    reason = f"Oylik sof pul oqimi taxminan {M(r.monthly_operating_net)}; to'lov uni " + (
        f"{P(r.dscr)} marta qoplaydi." if r.dscr else "qoplaydi."
    )
    rows = [
        {
            "label": "Oylik to'lov",
            "values": [M(r.payment) if r.payment else "—", M(r.max_safe_payment)],
        },
        {"label": "Summa", "values": [M(amount) if amount else "—", M(r.max_safe_amount)]},
    ]
    return envelope(
        facts={
            "rate": str(r.rate),
            "months": months,
            "amount": money(amount) if amount else None,
            "payment": money(r.payment) if r.payment else None,
            "max_safe_amount": money(r.max_safe_amount),
            "max_safe_payment": money(r.max_safe_payment),
            "dscr": str(r.dscr) if r.dscr else None,
            "monthly_operating_net": money(r.monthly_operating_net),
        },
        display={
            "payment": M(r.payment) if r.payment else "",
            "max_safe_amount": M(r.max_safe_amount),
            "max_safe_payment": M(r.max_safe_payment),
        },
        say=f"Xavfsiz kredit {uz.speech_amount(r.max_safe_amount)} gacha, oyiga {uz.speech_amount(r.max_safe_payment)}.",
        ui_blocks=[
            {
                "type": "scenario_table",
                "id": "loan",
                "title": "Kredit",
                "columns": ["So'ralgan", "Maksimal xavfsiz"],
                "rows": rows,
                "highlight": 1,
            },
            _plan_block("loan_plan", "Reja", plan),
        ],
        assumptions=_assumptions("loan_affordability", args, r.assumptions),
        answer=_answer(headline, reason, plan),
    )


# --- investments --------------------------------------------------------------------------
def investment_payback_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    b = ctx.business
    margin = (
        Decimal(args["margin"]) / 100
        if args.get("margin") is not None
        else 1 - base.variable_cost_ratio
    )
    price = Decimal(args["price_per_unit"]) if args.get("price_per_unit") else (b.avg_check or None)
    units = args.get("extra_units_per_day")
    extra_rev = Decimal(args["extra_revenue_month"]) if args.get("extra_revenue_month") else None
    if extra_rev is None and (units is None or price is None):
        qs = []
        if units is None:
            day_orders = b.orders_per_day or (
                int(sum(base.weekday_revenue) / 7 / price) if price else None
            )
            default = max(1, round(day_orders * 0.1)) if day_orders else None
            qs.append(
                {
                    "key": "extra_units_per_day",
                    "text": "Bu uskuna kuniga taxminan nechta qo'shimcha porsiya (mahsulot) beradi?",
                    "why": "qo'shimcha daromadni hisoblash uchun",
                    "default": str(default) if default else None,
                    "default_text": f"+{default} porsiya/kun" if default else "",
                }
            )
        if price is None:
            qs.append(
                {
                    "key": "price_per_unit",
                    "text": "Bitta porsiya (o'rtacha chek) necha so'm?",
                    "why": "daromadni so'mda hisoblash uchun",
                    "default": None,
                }
            )
        return _needs("investment_payback", args, qs[:2])
    if extra_rev is None:
        extra_rev = Decimal(units or 0) * Decimal(price or 0) * 30
    extra_cost = Decimal(args.get("extra_cost_month") or 0)
    assumptions = [
        A.Assumption("extra_units_per_day", f"Qo'shimcha: {units} ta/kun", str(units))
        if units is not None
        else A.Assumption(
            "extra_revenue_month", f"Qo'shimcha savdo: oyiga {M(extra_rev)}", str(extra_rev)
        ),
        A.Assumption("price_per_unit", f"O'rtacha chek: {M(Decimal(price))}", str(price))
        if price
        else None,
        A.Assumption(
            "margin",
            f"Marja: {(margin * 100).quantize(Decimal(1))}% (jadvaldan)",
            str((margin * 100).quantize(Decimal(1))),
        ),
        A.Assumption(
            "extra_cost_month",
            f"Qo'shimcha xarajat (gaz/svet): oyiga {M(extra_cost)}",
            str(extra_cost),
        ),
    ]
    try:
        r = A.investment_payback(
            ctx.cached.inp,
            Decimal(args["cost"]),
            extra_revenue_month=extra_rev,
            margin=margin,
            extra_cost_month=extra_cost,
            financing=args.get("financing", "cash"),
            n=args.get("n"),
            rate=args.get("rate"),
            months=args.get("months"),
            life_months=int(args.get("life_months") or 36),
            assumptions=[a for a in assumptions if a],
            base=base,
        )
    except EngineError as exc:
        raise ToolArgError(str(exc)) from exc
    names = {"pessimistic": "Pessimistik", "base": "Asosiy", "optimistic": "Optimistik"}
    bc = r.cases[1]

    def pts(c: A.PaybackCase) -> list[dict[str, Any]]:
        return [
            {"label": str(m), "value": int(v), "display": M(v)}
            for m, v in enumerate(c.cumulative[:25])
        ]

    be = bc.payback_months
    headline = (
        f"O'zini {be} oyda qoplaydi (asosiy holat), oyiga +{M(bc.monthly_net)}"
        if be
        else "Bu sharoitda o'zini qoplamaydi"
    )
    plan = [{"when": Dt(base.today), "action": "Uskunani sotib olish", "amount": M(r.cost)}]
    if be:
        plan.append(
            {
                "when": f"{be}-oy",
                "action": "Xarajat qoplanadi, keyin sof foyda",
                "amount": M(bc.monthly_net) + "/oy",
            }
        )
    plan.append(
        {
            "when": "Har oy",
            "action": "Qo'shimcha sotuvni (porsiyalarni) jadvalga alohida yozing — taxminni tekshirish uchun",
        }
    )
    blocks = [
        {
            "type": "payback_chart",
            "id": "payback",
            "title": "Jamg'arilgan natija (oylar)",
            "points": pts(bc),
            "break_even_index": be,
            "break_even_label": f"{be}-oyda o'zini qoplaydi" if be else "",
            "series": [{"name": names[c.name], "points": pts(c)} for c in r.cases],
        },
        {
            "type": "scenario_table",
            "id": "payback_cases",
            "title": "Uch holat (taxmin ±30%)",
            "columns": [names[c.name] for c in r.cases],
            "highlight": 1,
            "rows": [
                {"label": "Oylik sof foyda", "values": [M(c.monthly_net) for c in r.cases]},
                {
                    "label": "Qoplanish",
                    "values": [
                        f"{c.payback_months} oy" if c.payback_months else "yo'q" for c in r.cases
                    ],
                },
                {"label": "12 oylik ROI", "values": [f"{c.roi_12m_pct}%" for c in r.cases]},
            ],
        },
        _plan_block("payback_plan", "Reja", plan),
    ]
    return envelope(
        facts={
            "cost": money(r.cost),
            "cases": {
                c.name: {
                    "monthly_net": money(c.monthly_net),
                    "payback_months": c.payback_months,
                    "roi_12m_pct": str(c.roi_12m_pct),
                }
                for c in r.cases
            },
            "extra_revenue_month": money(extra_rev),
            "margin_pct": str((margin * 100).quantize(Decimal(1))),
            "extra_cost_month": money(extra_cost),
            "lowest": money(r.lowest),
            "lowest_date": r.lowest_date.isoformat(),
            "safe": r.safe,
        },
        display={"monthly_net": M(bc.monthly_net), "cost": M(r.cost), "lowest": M(r.lowest)},
        say=(
            f"Asosiy holatda {be} oyda o'zini qoplaydi."
            if be
            else "Bu sharoitda o'zini qoplamaydi."
        ),
        ui_blocks=blocks,
        assumptions=_assumptions("investment_payback", args, r.assumptions),
        answer=_answer(
            headline,
            f"Xariddan keyin kassada eng kami {M(r.lowest)} ({Dt(r.lowest_date)}) qoladi"
            + ("" if r.safe else " — xavfsiz chegaradan past")
            + ".",
            plan,
        ),
    )


# --- growth & price ------------------------------------------------------------------------
def revenue_growth_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    try:
        g = A.revenue_growth_target(
            ctx.cached.inp,
            Decimal(args["pct"]),
            int(args.get("months") or 3),
            ctx.business.avg_check,
            base=base,
        )
    except EngineError as exc:
        raise ToolArgError(str(exc)) from exc
    gaps = sum((gap for _, _, gap in g.weekday_room), Decimal(0)) or Decimal(1)
    per_day_week = g.extra_day * 7
    plan = []
    start = base.today + timedelta(days=(7 - base.today.weekday()) % 7 or 7)
    for i, (w, rev, gap) in enumerate(g.weekday_room):
        share = (per_day_week * gap / gaps).quantize(Decimal(1000))
        plan.append(
            {
                "when": f"{Dt(start + timedelta(weeks=i))} dan, {WD[w]} kunlari",
                "action": f"{WD[w].capitalize()} savdosini oshiring (hozir {M(rev)}/kun, eng kuchli kundan {M(gap)} past)",
                "amount": f"+{M(share)}/kun",
            }
        )
    plan.append(
        {
            "when": f"{g.months} oy ichida",
            "action": "Natijani har hafta jadvaldagi savdo bilan solishtiring",
            "amount": f"+{M(g.extra_month)}/oy",
        }
    )
    headline = f"+{g.pct}% uchun oyiga +{M(g.extra_month)} (kuniga +{M(g.extra_day)}) kerak"
    reason = f"Eng ko'p imkoniyat: {', '.join(WD[w] for w, _, _ in g.weekday_room)}. Shunda eng past qoldiq {M(g.lowest_before)} dan {M(g.lowest_after)} ga chiqadi."
    items = [
        {"label": "Oylik savdo hozir", "value": M(g.avg_month_revenue), "tone": "muted"},
        {
            "label": "Kerakli o'sish",
            "value": f"+{M(g.extra_month)}/oy",
            "note": f"kuniga +{M(g.extra_day)}",
            "tone": "success",
        },
        {"label": "180 kunda qo'shimcha pul", "value": M(g.cash_gain_horizon), "tone": "success"},
    ]
    if g.extra_orders_day:
        items.append(
            {"label": "Qo'shimcha buyurtma", "value": f"+{g.extra_orders_day}/kun", "tone": "muted"}
        )
    return envelope(
        facts={
            "pct": str(g.pct),
            "avg_month_revenue": money(g.avg_month_revenue),
            "extra_month": money(g.extra_month),
            "extra_day": money(g.extra_day),
            "extra_orders_day": g.extra_orders_day,
            "weekday_room": [
                {"weekday": WD[w], "revenue_day": money(r), "gap": money(gap)}
                for w, r, gap in g.weekday_room
            ],
            "lowest_before": money(g.lowest_before),
            "lowest_after": money(g.lowest_after),
            "cash_gain_horizon": money(g.cash_gain_horizon),
        },
        display={"extra_month": M(g.extra_month), "extra_day": M(g.extra_day)},
        say=f"Oyiga {uz.speech_amount(g.extra_month)} qo'shimcha savdo kerak, kuniga {uz.speech_amount(g.extra_day)}.",
        ui_blocks=[
            {"type": "metric_grid", "id": "growth", "title": f"Savdo +{g.pct}%", "items": items},
            _plan_block("growth_plan", "Reja", plan),
        ],
        assumptions=_assumptions("revenue_growth_target", args, g.assumptions),
        answer=_answer(headline, reason, plan),
    )


def price_change_tool(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    base = _base(ctx)
    if base is None:
        return insufficient()
    try:
        p = A.price_change(
            ctx.cached.inp,
            Decimal(args["pct"]),
            Decimal(args.get("volume_change_pct") or 0),
            base=base,
        )
    except EngineError as exc:
        raise ToolArgError(str(exc)) from exc
    headline = f"Narx {p.pct}%: oylik yalpi foyda {M(p.gross_profit_month_delta)} o'zgaradi"
    plan = [
        {
            "when": "Keyingi dushanbadan",
            "action": f"Narxni {p.pct}% o'zgartiring va 2 hafta sotuv hajmini kuzating",
            "amount": M(p.gross_profit_month_delta) + "/oy",
        }
    ]
    return envelope(
        facts={
            "pct": str(p.pct),
            "volume_pct": str(p.volume_pct),
            "margin_before": str(p.margin_before),
            "margin_after": str(p.margin_after),
            "gross_profit_month_delta": money(p.gross_profit_month_delta),
            "lowest_before": money(p.lowest_before),
            "lowest_after": money(p.lowest_after),
        },
        display={"delta": M(p.gross_profit_month_delta)},
        say=f"Oylik yalpi foyda {uz.speech_amount(p.gross_profit_month_delta)} o'zgaradi.",
        ui_blocks=[
            {
                "type": "metric_grid",
                "id": "price",
                "title": "Narx o'zgarishi",
                "items": [
                    {
                        "label": "Marja",
                        "value": f"{p.margin_before}% → {p.margin_after}%",
                        "tone": "muted",
                    },
                    {
                        "label": "Oylik yalpi foyda",
                        "value": M(p.gross_profit_month_delta),
                        "tone": "success" if p.gross_profit_month_delta > 0 else "warn",
                    },
                    {
                        "label": "Eng past qoldiq",
                        "value": f"{M(p.lowest_before)} → {M(p.lowest_after)}",
                        "tone": "muted",
                    },
                ],
            }
        ],
        assumptions=_assumptions("price_change", args, p.assumptions),
        answer=_answer(headline, f"Sotuv hajmi o'zgarishi taxmini: {p.volume_pct}%.", plan),
    )


NUM = {"type": "number"}
INT = {"type": "integer", "minimum": 1}
DATE = {"type": "string", "format": "date"}
ADVISOR_TOOLS: list[Tool] = [
    Tool(
        "business_snapshot",
        "Biznes holati: savdo, marja, eng katta xarajatlar, energiya, qarzlar, kuchli/zaif tomonlar (raqamlari bilan).",
        {"type": "object", "properties": {}},
        business_snapshot_tool,
    ),
    Tool(
        "when_can_afford",
        "Xaridni qachon xavfsiz qilish mumkin (180 kun ichida eng erta sana); bo'lib to'lash/kredit alternativalari; sana bo'lmasa kerakli jamg'arma va savdo o'sishi.",
        {
            "type": "object",
            "properties": {
                "amount": INT,
                "mode": {"type": "string", "enum": ["cash", "installments", "loan"]},
                "n": {"type": "integer", "minimum": 2, "maximum": 24},
                "rate": NUM,
                "months": {"type": "integer", "minimum": 1, "maximum": 120},
                "target_date": DATE,
            },
            "required": ["amount"],
        },
        when_can_afford_tool,
    ),
    Tool(
        "savings_goal",
        "Pul yig'ish maqsadi: summa qachon yig'iladi (majburiy to'lovlarni buzmasdan), muddatga yetish uchun oylik summa.",
        {"type": "object", "properties": {"amount": INT, "by_date": DATE}, "required": ["amount"]},
        savings_goal_tool,
    ),
    Tool(
        "record_debt",
        "Foydalanuvchi qarzini aytdi ('Shavkat akaga 30 mln qarzim bor'): qarzni tasdiqlash uchun yozadi va to'lash variantlarini solishtiradi.",
        {
            "type": "object",
            "properties": {
                "counterparty": {"type": "string", "maxLength": 120},
                "amount": INT,
                "due_date": DATE,
                "note": {"type": "string", "maxLength": 300},
                "n": {"type": "integer", "minimum": 2, "maximum": 12},
            },
            "required": ["counterparty", "amount"],
        },
        record_debt_tool,
    ),
    Tool(
        "debt_payoff",
        "Qarzni hozir / bo'lib / muddatida to'lash: har birida eng past qoldiq va qaysi biri xavfsiz.",
        {
            "type": "object",
            "properties": {
                "counterparty": {"type": "string", "maxLength": 120},
                "amount": INT,
                "due_date": DATE,
                "n": {"type": "integer", "minimum": 2, "maximum": 12},
            },
        },
        debt_payoff_tool,
    ),
    Tool(
        "loan_affordability",
        "Kredit: annuitet oylik to'lov, xavfsiz maksimal summa, qoplash koeffitsienti. Foiz noma'lum bo'lsa so'raydi.",
        {
            "type": "object",
            "properties": {
                "rate": NUM,
                "months": {"type": "integer", "minimum": 1, "maximum": 120},
                "amount": INT,
            },
        },
        loan_affordability_tool,
    ),
    Tool(
        "investment_payback",
        "Uskuna/investitsiya: oylik sof foyda, qoplanish oyi, 12 oylik ROI, 3 holat (pessimistik/asosiy/optimistik), kassa ta'siri.",
        {
            "type": "object",
            "properties": {
                "cost": INT,
                "financing": {"type": "string", "enum": ["cash", "installments", "loan"]},
                "n": {"type": "integer", "minimum": 2, "maximum": 24},
                "rate": NUM,
                "months": {"type": "integer", "minimum": 1, "maximum": 120},
                "extra_units_per_day": {"type": "integer", "minimum": 0, "maximum": 100000},
                "price_per_unit": NUM,
                "margin": NUM,
                "extra_revenue_month": NUM,
                "extra_cost_month": NUM,
                "life_months": {"type": "integer", "minimum": 6, "maximum": 120},
            },
            "required": ["cost"],
        },
        investment_payback_tool,
    ),
    Tool(
        "revenue_growth_target",
        "Savdoni X% oshirish: oyiga/kuniga qancha qo'shimcha kerak, qaysi hafta kunlarida imkoniyat ko'p, kassaga ta'siri.",
        {
            "type": "object",
            "properties": {"pct": NUM, "months": {"type": "integer", "minimum": 1, "maximum": 24}},
            "required": ["pct"],
        },
        revenue_growth_tool,
    ),
    Tool(
        "price_change",
        "Narxni X% o'zgartirish: marja va oylik foyda ta'siri; sotuv hajmi o'zgarishi taxmin sifatida.",
        {
            "type": "object",
            "properties": {"pct": NUM, "volume_change_pct": NUM},
            "required": ["pct"],
        },
        price_change_tool,
    ),
]

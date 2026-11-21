"""The DESIGN.md "Demo data" cash model, as engine input (spec §5.3 golden tests)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from apps.engine import DailyActual, EngineInput, ObligationIn, ParamsIn, RuleIn

M = Decimal(1_000_000)
TODAY = date(2026, 11, 21)
WEEKDAY_REVENUE = [Decimal(x) * M for x in ("5.8", "5.9", "6.0", "6.2", "7.6", "8.9", "8.2")]


def mln(x: str) -> Decimal:
    return (Decimal(x) * M).quantize(Decimal("0.01"))


def history(weeks: int = 8, noise: dict[int, list[Decimal]] | None = None) -> list[DailyActual]:
    """`weeks` x 7 days ending today; optional zero-sum noise per weekday."""
    days = weeks * 7
    start = TODAY - timedelta(days=days - 1)
    seen = [0] * 7
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        wd = d.weekday()
        rev = WEEKDAY_REVENUE[wd]
        if noise:
            rev += noise[wd][seen[wd]]
        seen[wd] += 1
        out.append(DailyActual(date=d, inflow=rev, outflow=rev * Decimal("0.45")))
    return out


def obligations() -> list[ObligationIn]:
    def ob(
        d: date, title: str, amount: str, priority: str, category: str, cp: str = ""
    ) -> ObligationIn:
        return ObligationIn(
            title=title,
            amount=mln(amount),
            due_date=d,
            priority=priority,  # type: ignore[arg-type]
            counterparty=cp,
            category=category,
        )

    return [
        ob(date(2026, 11, 25), "Ta'minotchi", "22", "deferrable", "supplier", "Agro Go'sht"),
        ob(date(2026, 12, 1), "Ijara", "15", "critical", "rent"),
        ob(date(2026, 12, 10), "Ish haqi", "45", "critical", "payroll"),
        ob(date(2026, 12, 10), "NBU kredit to'lovi", "18.5", "critical", "loan", "NBU"),
        ob(date(2026, 12, 15), "Soliq", "8", "critical", "tax"),
        ob(date(2026, 12, 25), "Ta'minotchi", "22", "deferrable", "supplier", "Agro Go'sht"),
        ob(date(2027, 1, 1), "Ijara", "15", "critical", "rent"),
        ob(date(2027, 1, 10), "Ish haqi", "45", "critical", "payroll"),
        ob(date(2027, 1, 10), "NBU kredit to'lovi", "18.5", "critical", "loan", "NBU"),
        ob(date(2027, 1, 15), "Soliq", "8", "critical", "tax"),
    ]


def golden_input(
    *, rules: list[RuleIn] | None = None, hist: list[DailyActual] | None = None, **overrides
) -> EngineInput:
    kwargs = dict(
        today=TODAY,
        opening_balance=mln("48.2"),
        history=hist if hist is not None else history(),
        obligations=obligations(),
        rules=rules or [],
        params=ParamsIn(variable_cost_ratio=Decimal("0.45")),
        safe_min=mln("10"),
        staff_count=15,
    )
    kwargs.update(overrides)
    return EngineInput(**kwargs)  # type: ignore[arg-type]

"""Day breakdown ("Qanday hisobladim?") and the discretionary spend limit."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .money import floor_to_step, from_tiyin
from .types import DayBreakdown, DayStatus, EngineError, ForecastResult

SPEND_LIMIT_STEP = Decimal(1_000_000)


def explain_day(base: ForecastResult, day: date) -> DayBreakdown:
    i = base.index(day)
    close = int(base.close[i])
    opening = int(base.close[i - 1]) if i > 0 else close + int(base.payments[0])
    revenue = int(base.revenue[i])
    variable = int(base.variable_cost[i])
    payments = tuple(p for p in base.obligations if (p.date == day if i > 0 else p.date <= day))
    closing = from_tiyin(close)
    status: DayStatus = "danger" if closing < 0 else "warn" if closing < base.safe_min else "ok"
    return DayBreakdown(
        date=day,
        opening=from_tiyin(opening),
        revenue=from_tiyin(revenue),
        variable_costs=from_tiyin(variable),
        net_trading=from_tiyin(revenue - variable),
        payments=payments,
        closing=closing,
        status=status,
        is_lowest_day=day == base.min_date,
    )


def spend_limit_until(
    base: ForecastResult, until: date, *, purchase_date: date | None = None
) -> Decimal:
    """How much can be spent on extras (one purchase) until `until`.

    limit = lowest balance from the purchase date to the end of the forecast - safe_min,
    rounded down to 1 mln, never below 0. A purchase lowers every later balance, so days
    after `until` still count. Golden case: 18,8 - 10 = 8,8 -> 8 000 000.
    """
    base.index(until)  # validates the date is in the window
    start = purchase_date or base.today
    if not base.today <= start <= until:
        raise EngineError("purchase_date must be between today and `until`")
    lowest = from_tiyin(int(base.close[base.index(start) :].min()))
    limit = floor_to_step(lowest - base.safe_min, SPEND_LIMIT_STEP)
    return max(limit, Decimal("0.00"))

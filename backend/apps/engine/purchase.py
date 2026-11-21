"""Purchase decision: "Can I spend X?" -> verdict + recommended option + alternatives.

Alternatives searched when buying as requested is not `yes`:
  (a) the earliest date within a 120-day horizon on which buying gives `yes`
      (only dates with at least 35 days of forecast after them, so a payroll day after
      the purchase is always visible);
  (b) 3 monthly instalments, rounded down to whole millions, remainder on the first
      (25 -> 9 + 8 + 8).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

import numpy as np

from .dates import add_months
from .forecast import forecast
from .money import to_tiyin
from .scenario import simulate
from .types import (
    Change,
    EngineError,
    EngineInput,
    ForecastResult,
    PurchaseDecision,
    PurchaseOption,
)

PURCHASE_HORIZON_DAYS = 120
MIN_DAYS_AFTER_PURCHASE = 35
INSTALLMENT_MONTHS = 3
MLN = Decimal(1_000_000)


def installment_schedule(
    start: date, amount: Decimal, months: int = INSTALLMENT_MONTHS
) -> tuple[tuple[date, Decimal], ...]:
    if months < 2:
        raise EngineError("installments must be >= 2")
    unit = MLN if amount >= MLN * months else Decimal(1000)
    part = (amount / months / unit).to_integral_value(rounding=ROUND_FLOOR) * unit
    first = amount - part * (months - 1)
    return tuple((add_months(start, k), first if k == 0 else part) for k in range(months))


def _option(
    base: ForecastResult,
    inp: EngineInput,
    kind: Literal["as_requested", "earliest_safe_date", "installments"],
    schedule: tuple[tuple[date, Decimal], ...],
    key_date: date | None,
) -> PurchaseOption:
    sc = simulate(base, inp, Change(kind="extra_expense", schedule=schedule))
    key = key_date or sc.first_shortage_date or sc.min_date
    return PurchaseOption(
        kind=kind,
        schedule=schedule,
        verdict=sc.verdict,
        min_balance=sc.min_balance,
        min_date=sc.min_date,
        first_shortage_date=sc.first_shortage_date,
        balance_on_key_date=sc.close_on(key),
    )


def earliest_safe_date(base: ForecastResult, amount: Decimal, after: date) -> date | None:
    """First day d > after where buying on d keeps every balance >= safe_min."""
    close = base.close
    n = len(close)
    safe = to_tiyin(base.safe_min)
    amt = to_tiyin(amount)
    prefix_min = np.minimum.accumulate(close)
    suffix_min = np.minimum.accumulate(close[::-1])[::-1]
    first = (after - base.today).days + 1
    last = n - 1 - MIN_DAYS_AFTER_PURCHASE
    if last < first:
        last = n - 1
    for i in range(max(first, 0), last + 1):
        before_ok = i == 0 or int(prefix_min[i - 1]) >= safe
        if before_ok and int(suffix_min[i]) - amt >= safe:
            return base.today + timedelta(days=i)
    return None


def evaluate_purchase(
    inp: EngineInput,
    amount: Decimal,
    on_date: date | None = None,
    installments: int | None = None,
    *,
    base: ForecastResult | None = None,
) -> PurchaseDecision:
    if not isinstance(amount, Decimal) or amount <= 0:
        raise EngineError("amount must be a positive Decimal")
    if base is None or base.horizon_days < PURCHASE_HORIZON_DAYS:
        base = forecast(inp, PURCHASE_HORIZON_DAYS)
    on = on_date or inp.today
    if not inp.today <= on <= base.end:
        raise EngineError("purchase date must be between today and the horizon end")

    if installments:
        schedule = installment_schedule(on, amount, installments)
    else:
        schedule = ((on, amount),)

    probe = _option(base, inp, "as_requested", schedule, None)
    key_date = probe.first_shortage_date or probe.min_date
    requested = probe
    base_on_key = base.close_on(key_date)

    if base.insufficient_data:
        return PurchaseDecision(
            amount=amount,
            verdict=None,
            key_date=key_date,
            requested=requested,
            recommended=None,
            alternatives=(),
            insufficient_data=True,
            base_balance_on_key_date=base_on_key,
        )

    alternatives: list[PurchaseOption] = []
    recommended: PurchaseOption | None = requested if requested.verdict == "yes" else None
    if recommended is None:
        safe_day = earliest_safe_date(base, amount, after=on)
        dated = (
            _option(base, inp, "earliest_safe_date", ((safe_day, amount),), key_date)
            if safe_day
            else None
        )
        split = (
            _option(base, inp, "installments", installment_schedule(on, amount), key_date)
            if not installments
            else None
        )
        alternatives = [o for o in (dated, split) if o is not None]
        if dated is not None:
            recommended = dated
        elif split is not None and split.verdict == "yes":
            recommended = split

    return PurchaseDecision(
        amount=amount,
        verdict=requested.verdict,
        key_date=key_date,
        requested=requested,
        recommended=recommended,
        alternatives=tuple(alternatives),
        insufficient_data=False,
        base_balance_on_key_date=base_on_key,
    )

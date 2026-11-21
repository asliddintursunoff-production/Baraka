""" "What if" scenarios: base series + a delta vector -> one cumsum (well under 5 ms)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from .forecast import compute_verdict
from .money import from_tiyin, to_tiyin
from .rules import norm
from .types import (
    BoolArray,
    Change,
    EngineError,
    EngineInput,
    ForecastResult,
    IntArray,
    ScenarioResult,
)


def _idx(base: ForecastResult, d: date) -> int:
    i = (d - base.today).days
    if not 0 <= i <= base.horizon_days:
        raise EngineError(f"{d} is outside the forecast window")
    return i


def _critical_counts(base: ForecastResult) -> IntArray:
    counts = np.zeros(base.horizon_days + 1, dtype=np.int64)
    for p in base.obligations:
        if p.priority == "critical":
            counts[max(0, (p.date - base.today).days)] += 1
    return counts


def delta_for(base: ForecastResult, inp: EngineInput, change: Change) -> tuple[IntArray, BoolArray]:
    """Cash delta per day (tiyin) and the critical-day mask under the change."""
    n = base.horizon_days + 1
    delta = np.zeros(n, dtype=np.int64)
    mask = base.critical_mask
    start = _idx(base, change.start_date) if change.start_date else 0
    value = change.value
    if not isinstance(value, Decimal):
        raise EngineError("change.value must be Decimal")

    if change.kind == "revenue_pct":
        if not Decimal(-100) <= value <= Decimal(500):
            raise EngineError("revenue_pct must be within -100..500")
        first = max(1, start)
        trading = (base.revenue - base.variable_cost)[first:].astype(np.float64)
        delta[first:] = np.rint(trading * float(value / 100)).astype(np.int64)

    elif change.kind == "new_staff":
        people = int(value)
        if people != value or not 1 <= people <= 1000:
            raise EngineError("new_staff value must be a whole number of people (1..1000)")
        if not inp.staff_count:
            raise EngineError("staff_count is unknown, cannot price new staff")
        payroll = [p for p in base.obligations if p.category == "payroll"]
        if not payroll:
            raise EngineError("no payroll payments in the forecast, cannot price new staff")
        mask = mask.copy()
        for p in payroll:
            i = max(0, (p.date - base.today).days)
            if i >= start:
                cost = (to_tiyin(p.amount) * people + inp.staff_count // 2) // inp.staff_count
                delta[i] -= cost
                mask[i] = True

    elif change.kind == "extra_expense":
        schedule = change.schedule or ((change.start_date or base.today, value),)
        for d, amount in schedule:
            if not isinstance(amount, Decimal) or amount <= 0:
                raise EngineError("expense amounts must be positive Decimals")
            if d < base.today:
                raise EngineError("an expense cannot be in the past")
            if d <= base.end:
                delta[_idx(base, d)] -= to_tiyin(amount)

    elif change.kind == "payment_delay":
        days = int(value)
        if days != value or not 1 <= days <= 365:
            raise EngineError("payment_delay value must be 1..365 days")
        if not change.counterparty:
            raise EngineError("payment_delay needs a counterparty")
        who = norm(change.counterparty)
        counts = _critical_counts(base)
        moved = False
        for p in base.obligations:
            i_old = max(0, (p.date - base.today).days)
            if norm(p.counterparty) != who or i_old < start:
                continue
            moved = True
            amt = to_tiyin(p.amount)
            delta[i_old] += amt
            new_date = p.date + timedelta(days=days)
            if p.priority == "critical":
                counts[i_old] -= 1
            if new_date <= base.end:
                i_new = (new_date - base.today).days
                delta[i_new] -= amt
                if p.priority == "critical":
                    counts[i_new] += 1
        if not moved:
            raise EngineError(f"no payments to {change.counterparty!r} in the forecast")
        mask = counts > 0
    else:  # pragma: no cover - Literal guards this
        raise EngineError(f"unknown change kind {change.kind!r}")
    return delta, mask


def simulate(base: ForecastResult, inp: EngineInput, change: Change) -> ScenarioResult:
    delta, mask = delta_for(base, inp, change)
    close = base.close + np.cumsum(delta)
    close.setflags(write=False)
    min_i = int(np.argmin(close))
    shortage = np.flatnonzero(close < 0)
    min_balance = from_tiyin(int(close[min_i]))
    verdict = (
        None if base.insufficient_data else compute_verdict(close, mask, to_tiyin(base.safe_min))
    )
    return ScenarioResult(
        change=change,
        today=base.today,
        close=close,
        critical_mask=mask,
        min_balance=min_balance,
        min_date=base.today + timedelta(days=min_i),
        first_shortage_date=(base.today + timedelta(days=int(shortage[0])))
        if shortage.size
        else None,
        verdict=verdict,
        base_min_balance=base.min_balance,
        delta_min=min_balance - base.min_balance,
    )

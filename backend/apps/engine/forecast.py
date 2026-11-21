"""Daily cash forecast: close(t) = close(t-1) + inflow(t) - outflow(t)  (spec §5.3).

- Sales: weekday average of the last 8 weeks x weekday_factors x rule multipliers.
- Variable costs: variable_cost_ratio x sales.
- Payments: on the exact (rule-adjusted) date. Unpaid payments dated today or earlier hit
  day 0, i.e. they reduce today's close.
- Uncertainty: per-weekday spread of daily sales, accumulated as sqrt(sum of variances)
  (sigma * sqrt(t) when the spread is constant). P10/P90 = close -/+ 1.2816 * that.
- Verdict (fixed rule, never the LLM):
    no    -> on a day with a critical payment the balance is below zero
    risky -> every critical payment is covered, but the lowest balance is below safe_min
    yes   -> the lowest balance is at least safe_min
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import numpy as np

from .history import HISTORY_WEEKS, revenue_model, weekday_revenue_decimal
from .money import from_tiyin, to_tiyin
from .rules import apply_rules
from .types import (
    BoolArray,
    Confidence,
    EngineError,
    EngineInput,
    ForecastResult,
    IntArray,
    PreparedObligation,
    Verdict,
)

Z_P10_P90 = 1.2816
MAX_HORIZON_DAYS = 366


def validate_input(inp: EngineInput, horizon_days: int) -> None:
    if not 1 <= horizon_days <= MAX_HORIZON_DAYS:
        raise EngineError(f"horizon_days must be 1..{MAX_HORIZON_DAYS}")
    for name in ("opening_balance", "safe_min"):
        if not isinstance(getattr(inp, name), Decimal):
            raise EngineError(f"{name} must be Decimal")
    if inp.safe_min < 0:
        raise EngineError("safe_min must be >= 0")
    vcr = inp.params.variable_cost_ratio
    if not isinstance(vcr, Decimal) or not Decimal(0) <= vcr < Decimal(1):
        raise EngineError("variable_cost_ratio must be a Decimal in [0, 1)")
    factors = inp.params.weekday_factors
    if len(factors) != 7 or any(not 0 <= f <= 5 for f in factors):
        raise EngineError("weekday_factors must be 7 values within 0..5")
    for o in inp.obligations:
        if not isinstance(o.amount, Decimal):
            raise EngineError(f"obligation {o.title!r}: amount must be Decimal")
    if inp.staff_count is not None and inp.staff_count <= 0:
        raise EngineError("staff_count must be positive")


def compute_verdict(close: IntArray, critical_mask: BoolArray, safe_min_tiyin: int) -> Verdict:
    if bool(np.any(close[critical_mask] < 0)):
        return "no"
    if int(close.min()) < safe_min_tiyin:
        return "risky"
    return "yes"


def _confidence(
    weeks: float, close: IntArray, band: IntArray, verdict: Verdict, safe_min_tiyin: int
) -> Confidence:
    """The only source of "confidence": history length and the distance of the lowest
    day from the decision threshold, measured in spreads (engine metric, not the LLM)."""
    data = 2 if weeks >= HISTORY_WEEKS else 1 if weeks >= 4 else 0
    i = int(np.argmin(close))
    threshold = 0 if verdict == "no" else safe_min_tiyin
    sigma = float(band[i]) / Z_P10_P90
    distance = abs(int(close[i]) - threshold)
    margin = (
        2 if sigma == 0 or distance / sigma >= Z_P10_P90 else 1 if distance / sigma >= 0.5 else 0
    )
    levels: tuple[Confidence, Confidence, Confidence] = ("low", "medium", "high")
    return levels[min(data, margin)]


def forecast(inp: EngineInput, horizon_days: int) -> ForecastResult:
    validate_input(inp, horizon_days)
    today = inp.today
    end = today + timedelta(days=horizon_days)
    n = horizon_days + 1

    prepared = apply_rules(inp.obligations, inp.rules, today=today, end=end)
    model = revenue_model(inp.history, today, inp.segment_prior)
    vcr = inp.params.variable_cost_ratio
    keep_share = float(Decimal(1) - vcr)
    factors = inp.params.weekday_factors

    revenue = np.zeros(n, dtype=np.int64)
    variable = np.zeros(n, dtype=np.int64)
    var_net = np.zeros(n, dtype=np.float64)  # variance of net trading per day (tiyin^2)
    for i in range(1, n):
        d = today + timedelta(days=i)
        wd = d.weekday()
        mult = factors[wd] * prepared.revenue_multiplier(d)
        rev = math.floor(model.weekday_revenue[wd] * mult + 0.5)
        revenue[i] = rev
        variable[i] = int((Decimal(rev) * vcr).to_integral_value(rounding=ROUND_HALF_EVEN))
        sigma_net = model.weekday_sigma[wd] * mult * keep_share
        var_net[i] = sigma_net * sigma_net

    payments = np.zeros(n, dtype=np.int64)
    critical = np.zeros(n, dtype=np.bool_)
    in_window: list[PreparedObligation] = []
    for p in prepared.obligations:
        if p.date > end:
            continue
        i = max(0, (p.date - today).days)
        payments[i] += to_tiyin(p.amount)
        if p.priority == "critical":
            critical[i] = True
        in_window.append(p)

    net = revenue - variable - payments
    close = to_tiyin(inp.opening_balance) + np.cumsum(net)
    band = np.rint(Z_P10_P90 * np.sqrt(np.cumsum(var_net))).astype(np.int64)
    for arr in (revenue, variable, payments, close, band, critical):
        arr.setflags(write=False)

    safe_t = to_tiyin(inp.safe_min)
    min_i = int(np.argmin(close))
    shortage = np.flatnonzero(close < 0)
    insufficient = model.insufficient
    verdict = None if insufficient else compute_verdict(close, critical, safe_t)
    return ForecastResult(
        today=today,
        horizon_days=horizon_days,
        safe_min=inp.safe_min,
        revenue=revenue,
        variable_cost=variable,
        payments=payments,
        close=close,
        band=band,
        critical_mask=critical,
        obligations=tuple(in_window),
        weekday_revenue=weekday_revenue_decimal(model),
        min_balance=from_tiyin(int(close[min_i])),
        min_date=today + timedelta(days=min_i),
        first_shortage_date=(today + timedelta(days=int(shortage[0]))) if shortage.size else None,
        verdict=verdict,
        insufficient_data=insufficient,
        confidence=None
        if verdict is None
        else _confidence(model.weeks, close, band, verdict, safe_t),
        weeks_of_history=model.weeks,
        segment_weight=model.segment_weight,
        variable_cost_ratio=vcr,
    )


def day_index(today: date, d: date, n: int) -> int:
    i = (d - today).days
    if not 0 <= i < n:
        raise EngineError(f"{d} is outside the forecast window")
    return i

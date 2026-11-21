"""Engine input/output types. Immutable; money is always `Decimal` at the boundary.

Internally the engine works in integer tiyin (1 so'm = 100 tiyin) with numpy int64
arrays; every public result converts back to `Decimal` with 2 decimal places.
Factors and ratios (not money) are floats/Decimals as documented per field.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import timedelta
from decimal import Decimal
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from .money import from_tiyin

Priority = Literal["critical", "deferrable", "discretionary"]
Verdict = Literal["yes", "risky", "no"]
Confidence = Literal["high", "medium", "low"]
RuleType = Literal["payment_shift", "recurring", "weekday_factor", "priority", "ignore"]
ChangeKind = Literal["revenue_pct", "new_staff", "extra_expense", "payment_delay"]
DayStatus = Literal["ok", "warn", "danger"]

PRIORITIES: tuple[Priority, ...] = ("critical", "deferrable", "discretionary")
RULE_TYPES: tuple[RuleType, ...] = (
    "payment_shift",
    "recurring",
    "weekday_factor",
    "priority",
    "ignore",
)

IntArray = npt.NDArray[np.int64]
BoolArray = npt.NDArray[np.bool_]


class EngineError(ValueError):
    """Invalid engine input (raised before any calculation)."""


# --- inputs ----------------------------------------------------------------------------
@dataclass(frozen=True)
class DailyActual:
    """One day of history: total sales inflow and total outflow (so'm)."""

    date: Date
    inflow: Decimal
    outflow: Decimal = Decimal(0)


@dataclass(frozen=True)
class TxnIn:
    """A single historical transaction, used only by `history.aggregate_daily`."""

    date: Date
    amount: Decimal  # always positive
    direction: Literal["in", "out"]
    category: str = ""
    counterparty: str = ""


@dataclass(frozen=True)
class ObligationIn:
    """A planned payment. `expected_date` (if set) overrides `due_date` for cash timing."""

    title: str
    amount: Decimal
    due_date: Date
    priority: Priority
    counterparty: str = ""
    category: str = ""  # payroll | loan | rent | tax | supplier | utility | other
    expected_date: Date | None = None
    id: str = ""


@dataclass(frozen=True)
class RuleIn:
    """A confirmed BusinessRule. `target`/`effect` shapes per type (see rules.py)."""

    type: RuleType
    target: Mapping[str, Any] = field(default_factory=dict)
    effect: Mapping[str, Any] = field(default_factory=dict)
    id: str = ""
    enabled: bool = True


@dataclass(frozen=True)
class ParamsIn:
    """Learned per-business parameters (factors are ratios, not money)."""

    weekday_factors: tuple[float, ...] = (1.0,) * 7  # Mon..Sun
    variable_cost_ratio: Decimal = Decimal(0)  # share of revenue spent as variable cost


@dataclass(frozen=True)
class SegmentPriorIn:
    """Anonymous segment knowledge: only the relative weekday shape (mean 1.0), no amounts."""

    weekday_shape: tuple[float, ...]  # Mon..Sun
    n_businesses: int


@dataclass(frozen=True)
class EngineInput:
    today: Date
    opening_balance: Decimal  # today's closing cash (today's sales already included)
    history: Sequence[DailyActual]
    obligations: Sequence[ObligationIn]
    rules: Sequence[RuleIn] = ()
    params: ParamsIn = field(default_factory=ParamsIn)
    segment_prior: SegmentPriorIn | None = None
    safe_min: Decimal = Decimal("10000000")
    staff_count: int | None = None  # for "new_staff" changes (average salary)
    last_payroll_amount: Decimal | None = None  # last paid payroll total (from history)
    # receipts known by date, outside daily sales (e.g. aggregator payouts on their cadence)
    scheduled_inflows: Sequence[tuple[Date, Decimal]] = ()

    def __post_init__(self) -> None:
        # Freeze sequences so a cached input can never be mutated by a caller.
        object.__setattr__(self, "history", tuple(self.history))
        object.__setattr__(self, "obligations", tuple(self.obligations))
        object.__setattr__(self, "rules", tuple(self.rules))
        object.__setattr__(self, "scheduled_inflows", tuple(self.scheduled_inflows))


@dataclass(frozen=True)
class Change:
    """A "what if". `value` meaning per kind:

    - revenue_pct:   percent change of sales from `start_date` (e.g. Decimal(-20))
    - new_staff:     number of extra people; cost = average salary on each payroll date
    - extra_expense: amount (so'm) on `start_date` (default today), or an explicit `schedule`
    - payment_delay: days to delay payments to `counterparty` (from `start_date`)
    """

    kind: ChangeKind
    value: Decimal = Decimal(0)
    start_date: Date | None = None
    counterparty: str | None = None
    schedule: tuple[tuple[Date, Decimal], ...] = ()


# --- outputs ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PreparedObligation:
    """An obligation after rules: `date` is when cash actually leaves."""

    title: str
    amount: Decimal
    date: Date
    due_date: Date
    priority: Priority
    counterparty: str
    category: str
    source: Literal["input", "rule"]
    rule_id: str = ""
    id: str = ""
    date_fixed: bool = False  # the data gave an explicit expected date; rules won't move it


@dataclass(frozen=True)
class Deferral:
    """Engine advice: move one non-critical payment by `days` to avoid a cash shortage."""

    obligation: PreparedObligation
    days: int
    new_date: Date
    resolves: bool  # True if no balance is below zero after the move


@dataclass(frozen=True)
class DayRow:
    date: Date
    open: Decimal
    inflow: Decimal  # forecast sales
    outflow: Decimal  # variable costs + payments
    close: Decimal
    p10: Decimal
    p90: Decimal


@dataclass(frozen=True, eq=False)
class ForecastResult:
    """Daily series for days 0..H (day 0 = today, its close = opening balance minus any
    unpaid payment dated today or earlier). Arrays are int64 tiyin, read-only."""

    today: Date
    horizon_days: int
    safe_min: Decimal
    revenue: IntArray
    variable_cost: IntArray
    payments: IntArray
    close: IntArray
    band: IntArray  # P10 = close - band, P90 = close + band
    critical_mask: BoolArray
    obligations: tuple[PreparedObligation, ...]
    weekday_revenue: tuple[Decimal, ...]  # model daily sales by weekday (Mon..Sun)
    min_balance: Decimal
    min_date: Date
    first_shortage_date: Date | None
    verdict: Verdict | None  # None when insufficient_data
    insufficient_data: bool
    confidence: Confidence | None
    weeks_of_history: float
    segment_weight: float
    variable_cost_ratio: Decimal
    deferrals: tuple[Deferral, ...] = ()  # only for a `risky` result with a shortage
    # set by the app's story view: a worse day beyond the visible horizon (date, balance)
    beyond: tuple[Date, Decimal] | None = None

    @property
    def end(self) -> Date:
        return self.today + timedelta(days=self.horizon_days)

    def index(self, d: Date) -> int:
        i = (d - self.today).days
        if not 0 <= i <= self.horizon_days:
            raise EngineError(f"{d} is outside the forecast window")
        return i

    def date_at(self, i: int) -> Date:
        return self.today + timedelta(days=i)

    def close_on(self, d: Date) -> Decimal:
        return from_tiyin(int(self.close[self.index(d)]))

    def daily(self) -> list[DayRow]:
        rows: list[DayRow] = []
        prev = int(self.close[0] + self.payments[0])  # opening balance
        for i in range(self.horizon_days + 1):
            close = int(self.close[i])
            band = int(self.band[i])
            rows.append(
                DayRow(
                    date=self.date_at(i),
                    open=from_tiyin(prev),
                    inflow=from_tiyin(int(self.revenue[i])),
                    outflow=from_tiyin(int(self.variable_cost[i] + self.payments[i])),
                    close=from_tiyin(close),
                    p10=from_tiyin(close - band),
                    p90=from_tiyin(close + band),
                )
            )
            prev = close
        return rows


@dataclass(frozen=True, eq=False)
class ScenarioResult:
    change: Change
    today: Date
    close: IntArray
    critical_mask: BoolArray
    min_balance: Decimal
    min_date: Date
    first_shortage_date: Date | None
    verdict: Verdict | None
    base_min_balance: Decimal
    delta_min: Decimal  # scenario min - base min
    deferrals: tuple[Deferral, ...] = ()

    def close_on(self, d: Date) -> Decimal:
        i = (d - self.today).days
        if not 0 <= i < len(self.close):
            raise EngineError(f"{d} is outside the forecast window")
        return from_tiyin(int(self.close[i]))


@dataclass(frozen=True)
class PurchaseOption:
    kind: Literal["as_requested", "earliest_safe_date", "installments"]
    schedule: tuple[tuple[Date, Decimal], ...]
    verdict: Verdict | None
    min_balance: Decimal
    min_date: Date
    first_shortage_date: Date | None
    balance_on_key_date: Decimal


@dataclass(frozen=True)
class PurchaseDecision:
    amount: Decimal
    verdict: Verdict | None  # of buying as requested
    key_date: Date  # the day that decides it (shortage day, else the lowest day)
    requested: PurchaseOption
    recommended: PurchaseOption | None
    alternatives: tuple[PurchaseOption, ...]
    insufficient_data: bool
    base_balance_on_key_date: Decimal


@dataclass(frozen=True)
class DayBreakdown:
    date: Date
    opening: Decimal
    revenue: Decimal
    variable_costs: Decimal
    net_trading: Decimal  # "Savdodan kiradi" = revenue - variable costs
    payments: tuple[PreparedObligation, ...]
    closing: Decimal
    status: DayStatus
    is_lowest_day: bool

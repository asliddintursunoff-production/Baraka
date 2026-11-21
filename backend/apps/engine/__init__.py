"""Financial Engine: pure Python. Must never import Django, ORM or network code.

The only place where balances, amounts, dates and verdicts are calculated (spec §1.1).
"""

from .deferral import suggest_deferrals
from .explain import explain_day, spend_limit_until
from .forecast import compute_verdict, forecast
from .history import aggregate_daily, revenue_model
from .purchase import earliest_safe_date, evaluate_purchase, installment_schedule
from .rules import apply_rules, norm
from .scenario import StaffCountUnknown, simulate
from .serialize import canonical_json, input_from_dict, input_to_dict, inputs_hash
from .types import (
    Change,
    DailyActual,
    DayBreakdown,
    DayRow,
    Deferral,
    EngineError,
    EngineInput,
    ForecastResult,
    ObligationIn,
    ParamsIn,
    PreparedObligation,
    PurchaseDecision,
    PurchaseOption,
    RuleIn,
    ScenarioResult,
    SegmentPriorIn,
    TxnIn,
)

__all__ = [
    "Change",
    "DailyActual",
    "DayBreakdown",
    "DayRow",
    "Deferral",
    "EngineError",
    "EngineInput",
    "ForecastResult",
    "ObligationIn",
    "ParamsIn",
    "PreparedObligation",
    "PurchaseDecision",
    "PurchaseOption",
    "RuleIn",
    "ScenarioResult",
    "SegmentPriorIn",
    "StaffCountUnknown",
    "TxnIn",
    "aggregate_daily",
    "apply_rules",
    "canonical_json",
    "compute_verdict",
    "earliest_safe_date",
    "evaluate_purchase",
    "explain_day",
    "forecast",
    "input_from_dict",
    "input_to_dict",
    "inputs_hash",
    "installment_schedule",
    "norm",
    "revenue_model",
    "simulate",
    "spend_limit_until",
    "suggest_deferrals",
]

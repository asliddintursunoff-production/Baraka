"""EngineInput <-> canonical JSON, and `inputs_hash` for the forecast cache.

Money is serialized as strings ("48200000.00"); dates as ISO strings. The same input
always yields the same JSON and hash, independent of dict order.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any

from .types import (
    DailyActual,
    EngineInput,
    ObligationIn,
    ParamsIn,
    RuleIn,
    SegmentPriorIn,
)

SCHEMA_VERSION = 1


def _money(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01'))}"


def input_to_dict(inp: EngineInput) -> dict[str, Any]:
    return {
        "v": SCHEMA_VERSION,
        "today": inp.today.isoformat(),
        "opening_balance": _money(inp.opening_balance),
        "safe_min": _money(inp.safe_min),
        "staff_count": inp.staff_count,
        "last_payroll_amount": _money(inp.last_payroll_amount)
        if inp.last_payroll_amount is not None
        else None,
        "history": [[h.date.isoformat(), _money(h.inflow), _money(h.outflow)] for h in inp.history],
        "obligations": [
            {
                "title": o.title,
                "amount": _money(o.amount),
                "due_date": o.due_date.isoformat(),
                "expected_date": o.expected_date.isoformat() if o.expected_date else None,
                "priority": o.priority,
                "counterparty": o.counterparty,
                "category": o.category,
                "id": o.id,
            }
            for o in inp.obligations
        ],
        "rules": [
            {
                "type": r.type,
                "target": dict(r.target),
                "effect": dict(r.effect),
                "id": r.id,
                "enabled": r.enabled,
            }
            for r in inp.rules
        ],
        "params": {
            "weekday_factors": list(inp.params.weekday_factors),
            "variable_cost_ratio": str(inp.params.variable_cost_ratio),
        },
        "segment_prior": None
        if inp.segment_prior is None
        else {
            "weekday_shape": list(inp.segment_prior.weekday_shape),
            "n_businesses": inp.segment_prior.n_businesses,
        },
    }


def input_from_dict(data: dict[str, Any]) -> EngineInput:
    if data.get("v") != SCHEMA_VERSION:
        raise ValueError(f"unsupported engine input version {data.get('v')!r}")
    sp = data.get("segment_prior")
    return EngineInput(
        today=date.fromisoformat(data["today"]),
        opening_balance=Decimal(data["opening_balance"]),
        safe_min=Decimal(data["safe_min"]),
        staff_count=data.get("staff_count"),
        last_payroll_amount=Decimal(data["last_payroll_amount"])
        if data.get("last_payroll_amount")
        else None,
        history=[
            DailyActual(date=date.fromisoformat(d), inflow=Decimal(i), outflow=Decimal(o))
            for d, i, o in data["history"]
        ],
        obligations=[
            ObligationIn(
                title=o["title"],
                amount=Decimal(o["amount"]),
                due_date=date.fromisoformat(o["due_date"]),
                expected_date=date.fromisoformat(o["expected_date"])
                if o.get("expected_date")
                else None,
                priority=o["priority"],
                counterparty=o.get("counterparty", ""),
                category=o.get("category", ""),
                id=o.get("id", ""),
            )
            for o in data["obligations"]
        ],
        rules=[
            RuleIn(
                type=r["type"],
                target=r.get("target", {}),
                effect=r.get("effect", {}),
                id=r.get("id", ""),
                enabled=r.get("enabled", True),
            )
            for r in data["rules"]
        ],
        params=ParamsIn(
            weekday_factors=tuple(float(x) for x in data["params"]["weekday_factors"]),
            variable_cost_ratio=Decimal(data["params"]["variable_cost_ratio"]),
        ),
        segment_prior=None
        if sp is None
        else SegmentPriorIn(
            weekday_shape=tuple(float(x) for x in sp["weekday_shape"]),
            n_businesses=int(sp["n_businesses"]),
        ),
    )


def canonical_json(inp: EngineInput) -> str:
    return json.dumps(input_to_dict(inp), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def inputs_hash(inp: EngineInput) -> str:
    return hashlib.sha256(canonical_json(inp).encode("utf-8")).hexdigest()

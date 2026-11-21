"""Business rules, applied before the forecast (spec §5.3).

Rule shapes (`RuleIn.target` / `RuleIn.effect`):

payment_shift   target {"counterparty": "Agro Go'sht"}          effect {"days": 15}
recurring       target {"title": "Svet", "counterparty"?, "category"?}
                effect {"amount": "2100000", "day_of_month": 3, "priority": "critical",
                        "from"?: "YYYY-MM-DD", "to"?: "YYYY-MM-DD"}
weekday_factor  target {"weekday": 4} or {"weekdays": [4, 5]}   (0 = Monday)
                effect {"multiplier": "1.15", "period"?: {"from": "03-14", "to": "03-21"}}
priority        target {"counterparty" | "title" | "category": "..."}  effect {"level": "critical"}
ignore          target {"counterparty" | "category": "..."}     effect {}

Order: recurring (generate) -> ignore -> priority -> payment_shift. A payment that already
has an explicit `expected_date` is never shifted again by a rule.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from .dates import in_period, on_day_of_month
from .types import (
    PRIORITIES,
    RULE_TYPES,
    EngineError,
    ObligationIn,
    PreparedObligation,
    Priority,
    RuleIn,
)

_APOSTROPHES = re.compile(r"[‘’ʻʼ`´]")
_SPACES = re.compile(r"\s+")


def norm(text: str) -> str:
    """Comparable form of a name: casefold, unified apostrophes, single spaces."""
    return _SPACES.sub(" ", _APOSTROPHES.sub("'", text)).strip().casefold()


@dataclass(frozen=True)
class PreparedRules:
    obligations: tuple[PreparedObligation, ...]
    revenue_multiplier: Callable[[date], float]
    applied: tuple[str, ...]  # ids of rules that changed something


def _decimal(value: Any, what: str) -> Decimal:
    if isinstance(value, float):
        raise EngineError(f"{what}: float is not allowed, use a string or int")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EngineError(f"{what}: not a number: {value!r}") from exc


def _int(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineError(f"{what}: integer expected, got {value!r}")
    return value


def _priority(value: Any) -> Priority:
    if value not in PRIORITIES:
        raise EngineError(f"priority must be one of {PRIORITIES}, got {value!r}")
    level: Priority = value
    return level


def _matches(ob: PreparedObligation, target: Mapping[str, Any], keys: Iterable[str]) -> bool:
    found = False
    for key in keys:
        if key in target:
            found = True
            if norm(str(getattr(ob, key))) != norm(str(target[key])):
                return False
    if not found:
        raise EngineError(f"rule target needs one of {tuple(keys)}")
    return True


def validate(rule: RuleIn) -> None:
    if rule.type not in RULE_TYPES:
        raise EngineError(f"unknown rule type {rule.type!r}")


def apply_rules(
    obligations: Iterable[ObligationIn],
    rules: Iterable[RuleIn],
    *,
    today: date,
    end: date,
) -> PreparedRules:
    active = [r for r in rules if r.enabled]
    for r in active:
        validate(r)
    applied: set[str] = set()

    prepared = [
        PreparedObligation(
            title=o.title,
            amount=o.amount,
            date=o.expected_date or o.due_date,
            due_date=o.due_date,
            priority=o.priority,
            counterparty=o.counterparty,
            category=o.category,
            source="input",
            id=o.id,
            date_fixed=o.expected_date is not None,
        )
        for o in obligations
        if o.amount > 0
    ]

    # 1. recurring: generate monthly payments not already present in the input that month
    for r in (r for r in active if r.type == "recurring"):
        title = str(r.target.get("title", "")).strip()
        if not title:
            raise EngineError("recurring rule needs target.title")
        amount = _decimal(r.effect.get("amount"), "recurring.amount")
        day = _int(r.effect.get("day_of_month"), "recurring.day_of_month")
        if not 1 <= day <= 31 or amount <= 0:
            raise EngineError("recurring rule needs day_of_month 1..31 and amount > 0")
        level = _priority(r.effect.get("priority", "critical"))
        valid_from = date.fromisoformat(r.effect["from"]) if r.effect.get("from") else None
        valid_to = date.fromisoformat(r.effect["to"]) if r.effect.get("to") else None
        counterparty = str(r.target.get("counterparty", ""))
        category = str(r.target.get("category", ""))
        y, m = today.year, today.month
        while (y, m) <= (end.year, end.month):
            d = on_day_of_month(y, m, day)
            exists = any(
                p.date.year == y
                and p.date.month == m
                and (
                    norm(p.title) == norm(title)
                    or (counterparty and norm(p.counterparty) == norm(counterparty))
                )
                for p in prepared
            )
            in_window = (
                today < d <= end
                and (valid_from is None or d >= valid_from)
                and (valid_to is None or d <= valid_to)
            )
            if in_window and not exists:
                prepared.append(
                    PreparedObligation(
                        title=title,
                        amount=amount,
                        date=d,
                        due_date=d,
                        priority=level,
                        counterparty=counterparty,
                        category=category,
                        source="rule",
                        rule_id=r.id,
                    )
                )
                applied.add(r.id)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    # 2. ignore
    for r in (r for r in active if r.type == "ignore"):
        keep = [
            p
            for p in prepared
            if not (p.source == "input" and _matches(p, r.target, ("counterparty", "category")))
        ]
        if len(keep) != len(prepared):
            applied.add(r.id)
        prepared = keep

    # 3. priority
    for r in (r for r in active if r.type == "priority"):
        level = _priority(r.effect.get("level"))
        for i, p in enumerate(prepared):
            if _matches(p, r.target, ("counterparty", "title", "category")) and p.priority != level:
                prepared[i] = replace(p, priority=level)
                applied.add(r.id)

    # 4. payment_shift
    for r in (r for r in active if r.type == "payment_shift"):
        days = _int(r.effect.get("days"), "payment_shift.days")
        for i, p in enumerate(prepared):
            if p.date_fixed:
                continue
            if _matches(p, r.target, ("counterparty", "category")):
                prepared[i] = replace(p, date=p.due_date + timedelta(days=days))
                applied.add(r.id)

    # weekday factors (revenue multipliers)
    factors: list[tuple[set[int], float, dict[str, str] | None]] = []
    for r in (r for r in active if r.type == "weekday_factor"):
        if "weekdays" in r.target:
            days_set = {_int(w, "weekday_factor.weekdays") for w in r.target["weekdays"]}
        else:
            days_set = {_int(r.target.get("weekday"), "weekday_factor.weekday")}
        if not days_set or not days_set <= set(range(7)):
            raise EngineError("weekday_factor weekdays must be 0..6")
        mult = _decimal(r.effect.get("multiplier"), "weekday_factor.multiplier")
        if not Decimal("0") <= mult <= Decimal("5"):
            raise EngineError("weekday_factor.multiplier must be within 0..5")
        period = r.effect.get("period")
        try:
            in_period(today, period)
        except ValueError as exc:
            raise EngineError(str(exc)) from exc
        factors.append((days_set, float(mult), period))
        window = (today + timedelta(days=i) for i in range(1, (end - today).days + 1))
        if any(d.weekday() in days_set and in_period(d, period) for d in window):
            applied.add(r.id)

    def revenue_multiplier(d: date) -> float:
        m = 1.0
        for days_set, mult, period in factors:
            if d.weekday() in days_set and in_period(d, period):
                m *= mult
        return m

    return PreparedRules(
        obligations=tuple(sorted(prepared, key=lambda p: (p.date, p.title))),
        revenue_multiplier=revenue_multiplier,
        applied=tuple(sorted(applied)),
    )

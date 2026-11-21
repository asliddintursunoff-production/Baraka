"""DB -> EngineInput -> ForecastResult, with snapshot + per-process cache (spec §5.6).

Request path (`get_forecast`): one indexed SELECT of the latest snapshot's hash. On a
cache hit that's all. On a miss, the snapshot's stored `inputs` JSON rebuilds the engine
input without touching the other tables. Only when there is no snapshot for today does
`refresh_forecast` read the business tables (~8 indexed queries) and store a new snapshot.
Call `refresh_forecast` after anything that changes the inputs (sync, rules, seed).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Q, Sum

from apps.engine import (
    EngineInput,
    ForecastResult,
    ObligationIn,
    ParamsIn,
    RuleIn,
    SegmentPriorIn,
    TxnIn,
    aggregate_daily,
    forecast,
    input_from_dict,
    input_to_dict,
    inputs_hash,
)
from apps.finance.models import CashAccount, Obligation, Transaction
from apps.knowledge.models import BusinessRule, ForecastParams, SegmentStats
from apps.telemetry import timing
from apps.tenancy.context import tenant_context, today_for
from apps.tenancy.models import Business

from .models import ForecastSnapshot

HORIZON_DAYS = 120  # covers the 7..90-day views and purchase checks (engine uses 120)
HISTORY_DAYS = 56
OBLIGATION_LOOKAHEAD_DAYS = HORIZON_DAYS + 60  # payments shifted into the window by rules


@dataclass(frozen=True)
class CachedForecast:
    business_id: int
    today: date
    inputs_hash: str
    inp: EngineInput
    result: ForecastResult
    snapshot_id: int | None
    has_cash: bool


_cache: dict[int, CachedForecast] = {}
_lock = threading.Lock()


def invalidate(business_id: int) -> None:
    with _lock:
        _cache.pop(business_id, None)


def _segment_prior(business: Business) -> SegmentPriorIn | None:
    if not business.segment_key:
        return None
    row = (
        SegmentStats.objects.filter(segment_key=business.segment_key, metric="weekday_shape")
        .values("value", "n_businesses")
        .first()
    )
    if not row or row["n_businesses"] < 5:
        return None
    return SegmentPriorIn(
        weekday_shape=tuple(float(x) for x in row["value"]), n_businesses=row["n_businesses"]
    )


def build_engine_input(business: Business) -> tuple[EngineInput, bool]:
    """Read the business tables. Returns (input, has_cash_account)."""
    today = today_for(business)
    with tenant_context(business):
        cash = CashAccount.objects.order_by("-as_of_date", "-id").first()
        opening = Decimal("0.00")
        if cash is not None:
            flows = Transaction.objects.filter(
                txn_date__gt=cash.as_of_date, txn_date__lte=today, is_actual=True
            ).aggregate(
                inflow=Sum("amount", filter=Q(direction="in")),
                outflow=Sum("amount", filter=Q(direction="out")),
            )
            opening = (
                Decimal(cash.opening_balance)
                + (flows["inflow"] or Decimal(0))
                - (flows["outflow"] or Decimal(0))
            ).quantize(Decimal("0.01"))

        rules = [
            RuleIn(
                type=r.type,
                target=r.target,
                effect=r.effect,
                id=str(r.pk),
            )
            for r in BusinessRule.objects.filter(enabled=True).order_by("id")
        ]
        start = today - timedelta(days=HISTORY_DAYS - 1)
        grouped = (
            Transaction.objects.filter(txn_date__gte=start, txn_date__lte=today, is_actual=True)
            .values("txn_date", "direction", "category", "counterparty__name")
            .annotate(total=Sum("amount"))
        )
        txns = [
            TxnIn(
                date=g["txn_date"],
                amount=g["total"],
                direction=g["direction"],
                category=g["category"] or "",
                counterparty=g["counterparty__name"] or "",
            )
            for g in grouped
        ]
        history = aggregate_daily(txns, rules, start=start, end=today)

        obligations = [
            ObligationIn(
                title=o.title,
                amount=Decimal(o.amount),
                due_date=o.due_date,
                expected_date=o.expected_date,
                priority=o.priority,
                counterparty=o.counterparty.name if o.counterparty else "",
                category=o.category,
                id=str(o.pk),
            )
            for o in Obligation.objects.filter(
                status=Obligation.Status.PLANNED,
                due_date__lte=today + timedelta(days=OBLIGATION_LOOKAHEAD_DAYS),
            )
            .select_related("counterparty")
            .order_by("due_date", "id")
        ]

        p = ForecastParams.objects.first()
        factors = tuple(
            float(x) for x in (p.weekday_factors if p and p.weekday_factors else [1.0] * 7)
        )
        params = ParamsIn(
            weekday_factors=factors,
            variable_cost_ratio=Decimal(p.variable_cost_ratio) if p else Decimal(0),
        )

        last_payroll_day = (
            Transaction.objects.filter(direction="out", category="payroll", txn_date__lte=today)
            .order_by("-txn_date")
            .values_list("txn_date", flat=True)
            .first()
        )
        last_payroll: Decimal | None = None
        if last_payroll_day:
            last_payroll = Transaction.objects.filter(
                direction="out",
                category="payroll",
                txn_date__gte=last_payroll_day - timedelta(days=3),
                txn_date__lte=last_payroll_day,
            ).aggregate(s=Sum("amount"))["s"]

    inp = EngineInput(
        today=today,
        opening_balance=opening,
        history=history,
        obligations=obligations,
        rules=rules,
        params=params,
        segment_prior=_segment_prior(business),
        safe_min=business.safe_min,
        staff_count=business.staff_count,
        last_payroll_amount=last_payroll,
    )
    return inp, cash is not None


def _snapshot_daily(result: ForecastResult) -> list[dict[str, Any]]:
    return [
        {
            "date": r.date.isoformat(),
            "open": str(r.open),
            "inflow": str(r.inflow),
            "outflow": str(r.outflow),
            "close": str(r.close),
            "p10": str(r.p10),
            "p90": str(r.p90),
        }
        for r in result.daily()
    ]


def refresh_forecast(business: Business) -> CachedForecast:
    """Recompute from the business tables; store a snapshot if the inputs changed."""
    inp, has_cash = build_engine_input(business)
    h = inputs_hash(inp)
    with timing.measure("engine"):
        result = forecast(inp, HORIZON_DAYS)
    with tenant_context(business):
        latest = (
            ForecastSnapshot.objects.order_by("-created_at").values("id", "inputs_hash").first()
        )
        if latest and latest["inputs_hash"] == h:
            snap_id = latest["id"]
        else:
            snap = ForecastSnapshot.objects.create(
                business=business,
                horizon_days=HORIZON_DAYS,
                daily=_snapshot_daily(result),
                min_balance=result.min_balance,
                min_date=result.min_date,
                first_shortage_date=result.first_shortage_date,
                verdict=result.verdict or "",
                inputs_hash=h,
                inputs={**input_to_dict(inp), "has_cash": has_cash},
            )
            snap_id = snap.pk
    cached = CachedForecast(business.pk, inp.today, h, inp, result, snap_id, has_cash)
    with _lock:
        _cache[business.pk] = cached
    return cached


def get_forecast(business: Business) -> CachedForecast:
    """Request path: 1 indexed SELECT on a hit (see module doc)."""
    today = today_for(business)
    with tenant_context(business):
        row = (
            ForecastSnapshot.objects.order_by("-created_at")
            .values("id", "inputs_hash", "created_at")
            .first()
        )
    if row is None:
        return refresh_forecast(business)
    created_local = row["created_at"].astimezone(ZoneInfo(business.timezone)).date()
    cached = _cache.get(business.pk)
    if cached and cached.inputs_hash == row["inputs_hash"] and cached.today == today:
        return cached
    if created_local != today:
        return refresh_forecast(business)  # a new day: today's sales/dates changed
    with tenant_context(business):
        data = (
            ForecastSnapshot.objects.filter(pk=row["id"]).values_list("inputs", flat=True).first()
        )
    if not data:
        return refresh_forecast(business)
    inp = input_from_dict(data)
    with timing.measure("engine"):
        result = forecast(inp, HORIZON_DAYS)
    cached = CachedForecast(
        business.pk,
        inp.today,
        row["inputs_hash"],
        inp,
        result,
        row["id"],
        bool(data.get("has_cash")),
    )
    with _lock:
        _cache[business.pk] = cached
    return cached

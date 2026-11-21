"""Backtest gate (A6): re-run the engine as of past month-ends using only data known then,
predict the next month-end cash and compare with the actual. Error must be <= 5 %.

The engine input is rebuilt the same way as the live one: opening cash rolled to `as_of`,
daily-sales history up to `as_of`, fixed payments and the loan schedule projected from cash
payments up to `as_of`, aggregator payouts on their observed cadence.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum

from apps.engine import aggregate_daily, forecast
from apps.engine.types import EngineInput, ObligationIn, ParamsIn, TxnIn
from apps.finance.models import CashAccount, Transaction
from apps.integrations.models import DataSource
from apps.tenancy.models import Business

MAX_ERROR = Decimal("0.05")
HISTORY_DAYS = 56
NOT_SALES = ("financing", "capex", "dividend", "avans", "agregator")


def _month_end(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def cash_on(d: date) -> Decimal | None:
    cash = CashAccount.objects.order_by("-as_of_date").first()
    if cash is None or d < cash.as_of_date:
        return None
    f = Transaction.objects.filter(
        is_actual=True, txn_date__gt=cash.as_of_date, txn_date__lte=d
    ).aggregate(
        i=Sum("amount", filter=Q(direction="in")), o=Sum("amount", filter=Q(direction="out"))
    )
    return Decimal(cash.opening_balance) + (f["i"] or Decimal(0)) - (f["o"] or Decimal(0))


def input_as_of(business: Business, as_of: date, source_id: int | None) -> EngineInput | None:
    """Inside the tenant context. None when there is no opening cash before `as_of`."""
    from apps.ingestion.finmodel import aggregator_payouts, planned_payments
    from apps.ingestion.pipeline import variable_cost_ratio

    opening = cash_on(as_of)
    if opening is None:
        return None
    start = as_of - timedelta(days=HISTORY_DAYS - 1)
    grouped = (
        Transaction.objects.filter(txn_date__gte=start, txn_date__lte=as_of, is_actual=True)
        .exclude(direction="in", category__in=NOT_SALES)
        .values("txn_date", "direction", "category")
        .annotate(total=Sum("amount"))
    )
    txns = [
        TxnIn(
            date=g["txn_date"],
            amount=g["total"],
            direction=g["direction"],
            category=g["category"] or "",
        )
        for g in grouped
    ]
    obligations = [
        ObligationIn(
            title=x["title"],
            amount=x["amount"],
            due_date=x["due_date"],
            priority=x["priority"],
            counterparty=x["counterparty"] or "",
            category=x["category"],
        )
        for x in planned_payments(as_of, source_id)
    ]
    return EngineInput(
        today=as_of,
        opening_balance=opening.quantize(Decimal("0.01")),
        history=aggregate_daily(txns, (), start=start, end=as_of),
        obligations=obligations,
        params=ParamsIn(
            weekday_factors=(1.0,) * 7, variable_cost_ratio=variable_cost_ratio(as_of) or Decimal(0)
        ),
        safe_min=Decimal(business.safe_min_balance),
        scheduled_inflows=aggregator_payouts(as_of),
    )


def run(business: Business, months: int = 2) -> list[dict[str, Any]]:
    """The last `months` complete months with data: as of the previous month-end -> this one."""
    last = (
        Transaction.objects.filter(is_actual=True)
        .order_by("-txn_date")
        .values_list("txn_date", flat=True)
        .first()
    )
    if last is None:
        return []
    src = DataSource.objects.exclude(summary={}).first()
    source_id = src.pk if src else None
    target = (
        _month_end(last)
        if last == _month_end(last)
        else _month_end(last.replace(day=1) - timedelta(days=1))
    )
    rows: list[dict[str, Any]] = []
    for _ in range(months):
        as_of = target.replace(day=1) - timedelta(days=1)
        inp = input_as_of(business, as_of, source_id)
        actual = cash_on(target)
        if inp is None or actual is None or not actual:
            break
        result = forecast(inp, (target - as_of).days)
        # one-offs (capex, dividends, owner money, loan in/out) are excluded from the model by
        # design; the realised ones are added back so the gate measures the recurring forecast
        one = Transaction.objects.filter(
            is_actual=True,
            txn_date__gt=as_of,
            txn_date__lte=target,
            category__in=("capex", "dividend", "financing"),
        ).aggregate(
            i=Sum("amount", filter=Q(direction="in")), o=Sum("amount", filter=Q(direction="out"))
        )
        predicted = result.close_on(target) + (one["i"] or Decimal(0)) - (one["o"] or Decimal(0))
        err = abs(predicted - actual) / abs(actual)
        rows.append(
            {
                "as_of": as_of.isoformat(),
                "target": target.isoformat(),
                "predicted": str(predicted),
                "actual": str(actual.quantize(Decimal("0.01"))),
                "error_pct": str((err * 100).quantize(Decimal("0.01"))),
                "ok": err <= MAX_ERROR,
                "one_offs": str(
                    ((one["i"] or Decimal(0)) - (one["o"] or Decimal(0))).quantize(Decimal("0.01"))
                ),
            }
        )
        target = as_of
    return list(reversed(rows))

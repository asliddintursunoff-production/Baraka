"""History -> daily totals -> revenue model (weekday averages, spread, segment blend)."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .money import from_tiyin, to_tiyin
from .rules import norm
from .types import DailyActual, RuleIn, SegmentPriorIn, TxnIn

HISTORY_WEEKS = 8
MIN_HISTORY_WEEKS = 2
FALLBACK_SIGMA_SHARE = 0.25  # spread used for a weekday with < 2 observations


def aggregate_daily(
    txns: Iterable[TxnIn], rules: Iterable[RuleIn] = (), *, start: date, end: date
) -> tuple[DailyActual, ...]:
    """Sum transactions per day (inclusive range), skipping `ignore` rules' targets.

    Days without any transaction are returned with zero totals, so the series is gap-free.
    """
    ignored_cat: set[str] = set()
    ignored_cp: set[str] = set()
    for r in rules:
        if r.enabled and r.type == "ignore":
            if "category" in r.target:
                ignored_cat.add(norm(str(r.target["category"])))
            if "counterparty" in r.target:
                ignored_cp.add(norm(str(r.target["counterparty"])))
    inflow: dict[date, int] = defaultdict(int)
    outflow: dict[date, int] = defaultdict(int)
    for t in txns:
        if not start <= t.date <= end:
            continue
        if norm(t.category) in ignored_cat or (
            t.counterparty and norm(t.counterparty) in ignored_cp
        ):
            continue
        bucket = inflow if t.direction == "in" else outflow
        bucket[t.date] += to_tiyin(abs(t.amount))
    days = (end - start).days + 1
    return tuple(
        DailyActual(
            date=d,
            inflow=from_tiyin(inflow.get(d, 0)),
            outflow=from_tiyin(outflow.get(d, 0)),
        )
        for d in (start + timedelta(days=i) for i in range(days))
    )


@dataclass(frozen=True)
class RevenueModel:
    weekday_revenue: tuple[int, ...]  # tiyin per day, Mon..Sun (before weekday_factors)
    weekday_sigma: tuple[int, ...]  # tiyin, spread of daily sales per weekday
    weeks: float  # weeks of history inside the window
    segment_weight: float
    insufficient: bool


def _round(x: float) -> int:
    return math.floor(x + 0.5)


def revenue_model(
    history: Sequence[DailyActual],
    today: date,
    segment_prior: SegmentPriorIn | None,
) -> RevenueModel:
    """Daily sales by weekday from the last 8 weeks (window ends today, inclusive).

    Days inside the observed span that have no row count as zero sales. With < 8 weeks
    the shape is blended with the segment prior: w_segment = 1 - min(1, weeks / 8).
    """
    window_start = today - timedelta(days=HISTORY_WEEKS * 7 - 1)
    by_day = {h.date: to_tiyin(h.inflow) for h in history if window_start <= h.date <= today}
    if not by_day:
        return RevenueModel((0,) * 7, (0,) * 7, 0.0, 0.0, insufficient=True)
    span_start = min(by_day)
    span_days = (today - span_start).days + 1
    weeks = span_days / 7

    values: list[list[int]] = [[] for _ in range(7)]
    for i in range(span_days):
        d = span_start + timedelta(days=i)
        values[d.weekday()].append(by_day.get(d, 0))

    own: list[float | None] = [(sum(v) / len(v)) if v else None for v in values]
    overall = sum(sum(v) for v in values) / span_days

    seg_w = 0.0
    if segment_prior is not None and weeks < HISTORY_WEEKS:
        seg_w = 1.0 - min(1.0, weeks / HISTORY_WEEKS)
        shape = list(segment_prior.weekday_shape)
        if len(shape) != 7 or any(s < 0 for s in shape) or sum(shape) <= 0:
            raise ValueError("segment weekday_shape must have 7 non-negative values")
        mean_shape = sum(shape) / 7
        prior = [overall * s / mean_shape for s in shape]
        blended = []
        for w in range(7):
            o = own[w]
            blended.append(prior[w] if o is None else (1 - seg_w) * o + seg_w * prior[w])
    else:
        blended = [overall if o is None else o for o in own]

    sigma: list[int] = []
    for w in range(7):
        v = values[w]
        if len(v) >= 2:
            mean = sum(v) / len(v)
            var = sum((x - mean) ** 2 for x in v) / (len(v) - 1)
            sigma.append(_round(math.sqrt(var)))
        else:
            sigma.append(_round(blended[w] * FALLBACK_SIGMA_SHARE))

    insufficient = weeks < MIN_HISTORY_WEEKS and segment_prior is None
    return RevenueModel(
        weekday_revenue=tuple(_round(x) for x in blended),
        weekday_sigma=tuple(sigma),
        weeks=round(weeks, 2),
        segment_weight=round(seg_w, 4),
        insufficient=insufficient,
    )


def weekday_revenue_decimal(model: RevenueModel) -> tuple[Decimal, ...]:
    return tuple(from_tiyin(v) for v in model.weekday_revenue)

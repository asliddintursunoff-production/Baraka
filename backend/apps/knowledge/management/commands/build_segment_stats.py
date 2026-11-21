"""`manage.py build_segment_stats`: anonymous aggregates per segment (>= 5 businesses).

For every `segment_key` with at least SEGMENT_MIN_BUSINESSES businesses:
  weekday_shape        mean relative sales by weekday (Mon..Sun, mean 1.0) -> engine prior
  variable_cost_ratio  median share of non-obligation spending in sales
Only shapes and ratios are stored: no names, no amounts, no business ids. No LLM.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum

from apps.finance.models import Transaction
from apps.ingestion.pipeline import OBLIGATION_CATEGORIES
from apps.knowledge.models import SegmentStats
from apps.tenancy.context import today_for
from apps.tenancy.models import Business
from config import app_settings as cfg

WEEKS = 8


def weekday_shape(business: Business) -> list[float] | None:
    end = today_for(business)
    start = end - timedelta(weeks=WEEKS)
    sums = [0.0] * 7
    rows = (
        Transaction.unscoped.filter(
            business=business, direction="in", txn_date__gt=start, txn_date__lte=end
        )
        .values("txn_date")
        .annotate(s=Sum("amount"))
    )
    days = 0
    for r in rows:
        sums[r["txn_date"].weekday()] += float(r["s"])
        days += 1
    if days < 28 or not any(sums):
        return None
    mean = sum(sums) / 7
    return [round(x / mean, 4) for x in sums]


def cost_ratio(business: Business) -> float | None:
    end = today_for(business)
    agg = Transaction.unscoped.filter(
        business=business, txn_date__gt=end - timedelta(weeks=WEEKS), txn_date__lte=end
    ).aggregate(
        inflow=Sum("amount", filter=Q(direction="in")),
        var=Sum("amount", filter=Q(direction="out") & ~Q(category__in=OBLIGATION_CATEGORIES)),
    )
    inflow, var = agg["inflow"] or Decimal(0), agg["var"] or Decimal(0)
    return float(var / inflow) if inflow > 0 else None


class Command(BaseCommand):
    help = "Rebuild anonymous segment statistics (k >= 5 businesses)."

    def handle(self, *args: Any, **opts: Any) -> None:
        groups: dict[str, list[Business]] = defaultdict(list)
        for b in Business.objects.exclude(segment_key="").exclude(seed_tag="demo_user"):
            groups[b.segment_key].append(b)
        for key, members in groups.items():
            shapes = [s for b in members if (s := weekday_shape(b))]
            ratios = [r for b in members if (r := cost_ratio(b)) is not None]
            if len(shapes) >= cfg.SEGMENT_MIN_BUSINESSES:
                avg = [round(statistics.fmean(s[i] for s in shapes), 4) for i in range(7)]
                SegmentStats.objects.update_or_create(
                    segment_key=key,
                    metric="weekday_shape",
                    defaults={"value": avg, "n_businesses": len(shapes)},
                )
                self.stdout.write(f"{key}: weekday_shape {avg} (n={len(shapes)})")
            if len(ratios) >= cfg.SEGMENT_MIN_BUSINESSES:
                med = round(statistics.median(ratios), 4)
                SegmentStats.objects.update_or_create(
                    segment_key=key,
                    metric="variable_cost_ratio",
                    defaults={"value": med, "n_businesses": len(ratios)},
                )
                self.stdout.write(f"{key}: variable_cost_ratio {med} (n={len(ratios)})")
            if len(shapes) < cfg.SEGMENT_MIN_BUSINESSES:
                self.stdout.write(f"{key}: skipped, only {len(shapes)} businesses with history")

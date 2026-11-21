"""`manage.py latency_report` (`make latency`): latency + AI cost table, no AI calls.

1. Page APIs measured in-process now (demo owner, 20 requests each): p50 / p95.
2. Chat and voice events recorded by the app (LatencyEvent, last 7 days): p50 / p95.
3. AI spend from AiUsage: per kind/model calls, tokens, seconds, cost; today / total vs limits.
Prints Markdown (paste into docs/LATENCY.md).
"""

from __future__ import annotations

import statistics
import time
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.test import Client
from django.utils import timezone

from apps.ai import budget
from apps.telemetry.models import AiUsage, LatencyEvent
from config import app_settings as cfg

PAGES = [
    "/api/dashboard",
    "/api/forecast",
    "/api/calendar",
    "/api/knowledge",
    "/api/sources",
    "/api/alerts",
]


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(q * (len(xs) - 1)))]


class Command(BaseCommand):
    help = "p50/p95 latency per page/channel + AI cost table (no AI calls)."

    def handle(self, *args: Any, **opts: Any) -> None:
        out = self.stdout.write
        out(f"## Latency report — {timezone.localtime():%Y-%m-%d %H:%M}\n")
        user = get_user_model().objects.filter(email="demo@demo.uz").first()
        if user:
            c = Client(HTTP_HOST="localhost")
            c.force_login(user)
            out("| Page API (in-process, n=20) | p50 ms | p95 ms |\n|---|---|---|")
            for url in PAGES:
                c.get(url)  # warm
                ms = []
                for _ in range(20):
                    t0 = time.perf_counter()
                    c.get(url)
                    ms.append((time.perf_counter() - t0) * 1000)
                out(f"| `{url}` | {pct(ms, 0.5):.0f} | {pct(ms, 0.95):.0f} |")
            ms, code = [], 0
            for _ in range(10):
                t0 = time.perf_counter()
                code = c.post(
                    "/api/simulate", {"preset": "buy"}, content_type="application/json"
                ).status_code
                ms.append((time.perf_counter() - t0) * 1000)
            out(
                f"| `/api/simulate` (25 mln preset, n=10, HTTP {code}) | {pct(ms, 0.5):.0f} | {pct(ms, 0.95):.0f} |\n"
            )
        since = timezone.now() - timedelta(days=7)
        rows = (
            LatencyEvent.objects.filter(created_at__gte=since)
            .values("channel", "name")
            .annotate(n=Count("id"))
            .order_by("channel", "name")
        )
        if rows:
            out("| Recorded event (7 days) | n | p50 ms | p95 ms |\n|---|---|---|---|")
            for r in rows:
                ms = list(
                    LatencyEvent.objects.filter(
                        created_at__gte=since, channel=r["channel"], name=r["name"]
                    ).values_list("ms", flat=True)
                )
                out(
                    f"| {r['channel']} · {r['name']} | {r['n']} | {statistics.median(ms):.0f} | {pct(ms, 0.95):.0f} |"
                )
            out("")
        out(
            "| AI usage (all time) | calls | in tok | out tok | sec | cost $ |\n|---|---|---|---|---|---|"
        )
        for u in (
            AiUsage.objects.values("kind", "model")
            .annotate(
                n=Count("id"),
                i=Sum("input_tokens"),
                o=Sum("output_tokens"),
                s=Sum("seconds"),
                c=Sum("cost_usd"),
            )
            .order_by("-c")
        ):
            out(
                f"| {u['kind']} · {u['model']} | {u['n']} | {u['i']} | {u['o']} | {u['s']} | {Decimal(u['c']):.4f} |"
            )
        today, total = budget.spent()
        out(
            f"\n**AI spend:** today ${today:.4f} / ${cfg.AI_DAILY_BUDGET_USD} · total ${total:.4f} / ${cfg.AI_TOTAL_BUDGET_USD} "
            f"(estimated from `AI_PRICES_PER_M_TOKENS`, profile `{budget.profile()}`)"
        )

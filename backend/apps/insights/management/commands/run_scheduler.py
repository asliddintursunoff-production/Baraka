"""`manage.py run_scheduler`: the scheduler process (same image as web, other command).

A plain asyncio loop, no task-queue library. Jobs are registered in later milestones:
  every 15 min  sync_all          (M5)
  08:00         daily_brief       (M6)
  03:00         nightly_learning  (M7)
Each job runs per business under a Postgres advisory lock; one failing business never
stops the others.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand

from config import app_settings as cfg

log = logging.getLogger("scheduler")
TICK_S = 30


def sync_all() -> dict[str, int]:
    """Every business with confirmed auto-sync sources; one failure never stops the others."""
    from django.db import connections

    from apps.ingestion.sync import sync_business
    from apps.integrations.models import DataSource
    from apps.tenancy.models import Business

    done = failed = 0
    ids = set(
        DataSource.unscoped.filter(confirmed=True, auto_sync=True)
        .exclude(status__in=[DataSource.Status.PAUSED, DataSource.Status.REAUTH])
        .values_list("business_id", flat=True)
    )
    for business in Business.objects.filter(pk__in=ids):
        try:
            s = sync_business(business, trigger="schedule", force=False, progress=lambda t, p: None)
            done += 1
            if s.rows_added or s.rows_deleted:
                _log(
                    "sync_changed", business=business.pk, added=s.rows_added, deleted=s.rows_deleted
                )
        except Exception as exc:  # one business never blocks the rest
            failed += 1
            log.exception("sync_all failed for business %s: %s", business.pk, exc)
    connections.close_all()
    return {"businesses": done, "failed": failed}


def briefs_all() -> dict[str, int]:
    """08:00 brief for every business with members (templates only, no LLM)."""
    from django.db import connections

    from apps.insights.alerts import daily_brief, evaluate_alerts
    from apps.tenancy.models import Business, Membership

    done = failed = 0
    for business in Business.objects.filter(
        pk__in=Membership.objects.values_list("business_id", flat=True)
    ):
        try:
            evaluate_alerts(business)
            daily_brief(business)
            done += 1
        except Exception as exc:
            failed += 1
            log.exception("daily brief failed for business %s: %s", business.pk, exc)
    connections.close_all()
    return {"businesses": done, "failed": failed}


def _log(event: str, **fields: Any) -> None:
    log.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


class Command(BaseCommand):
    help = "Run background jobs (sync, daily brief, nightly learning)."

    def handle(self, *args: Any, **opts: Any) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        _log(
            "scheduler_started",
            sync_interval_min=cfg.SYNC_INTERVAL_MIN,
            jobs=["sync_all", "daily_brief"],
        )
        next_sync = 0.0
        last_brief: date | None = None
        while not stop.is_set():
            local = datetime.now(ZoneInfo("Asia/Tashkent"))
            if local.time() >= cfg.DAILY_BRIEF_AT and last_brief != local.date():
                result = await sync_to_async(briefs_all, thread_sensitive=False)()
                _log("daily_brief", **result)
                last_brief = local.date()
            now = time.monotonic()
            if now >= next_sync:
                t0 = time.perf_counter()
                result = await sync_to_async(sync_all, thread_sensitive=False)()
                _log("sync_all", ms=round((time.perf_counter() - t0) * 1000, 1), **result)
                next_sync = now + cfg.SYNC_INTERVAL_MIN * 60
            try:
                await asyncio.wait_for(stop.wait(), timeout=TICK_S)
            except TimeoutError:
                pass
        _log("scheduler_stopped")

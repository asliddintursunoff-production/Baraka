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
from typing import Any

from django.core.management.base import BaseCommand

from config import app_settings as cfg

log = logging.getLogger("scheduler")
TICK_S = 30


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
        _log("scheduler_started", sync_interval_min=cfg.SYNC_INTERVAL_MIN, jobs=[])
        while not stop.is_set():
            t0 = time.perf_counter()
            # Jobs are added in M5-M7.
            _log("tick", ms=round((time.perf_counter() - t0) * 1000, 1))
            try:
                await asyncio.wait_for(stop.wait(), timeout=TICK_S)
            except TimeoutError:
                pass
        _log("scheduler_stopped")

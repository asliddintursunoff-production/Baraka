"""Per-request timing buckets for the `Server-Timing` header (db, engine, llm, embed)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

# A mutable dict per request; asgiref copies the context into sync_to_async threads,
# so mutations made there (e.g. DB timings) are visible to the middleware.
_timings: ContextVar[dict[str, float] | None] = ContextVar("server_timings", default=None)


def start_request() -> dict[str, float]:
    bucket: dict[str, float] = {}
    _timings.set(bucket)
    return bucket


def add(name: str, ms: float) -> None:
    bucket = _timings.get()
    if bucket is not None:
        bucket[name] = bucket.get(name, 0.0) + ms


@contextmanager
def measure(name: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        add(name, (time.perf_counter() - t0) * 1000)


def db_execute_wrapper(
    execute: Callable[..., Any], sql: str, params: Any, many: bool, context: dict[str, Any]
) -> Any:
    t0 = time.perf_counter()
    try:
        return execute(sql, params, many, context)
    finally:
        add("db", (time.perf_counter() - t0) * 1000)


def format_header(bucket: dict[str, float], total_ms: float) -> str:
    parts = [f"{name};dur={ms:.1f}" for name, ms in bucket.items()]
    parts.append(f"total;dur={total_ms:.1f}")
    return ", ".join(parts)

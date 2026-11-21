"""LLM calls with the approved fallback chain + an in-process circuit breaker.

No SDK retries here: on 429/503/504 or a passed deadline we move to the next model at
once (waiting on a busy model would blow the chat latency budget).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config import app_settings as cfg

from .gemini import scrub

log = logging.getLogger(__name__)
FAILOVER_CODES = {429, 500, 502, 503, 504}


class AllModelsFailed(RuntimeError):
    pass


class _Breaker:
    def __init__(self) -> None:
        self.errors: dict[str, deque[float]] = {}
        self.open_until: dict[str, float] = {}

    def available(self, model: str, now: float) -> bool:
        return self.open_until.get(model, 0.0) <= now

    def failure(self, model: str, now: float) -> None:
        q = self.errors.setdefault(model, deque())
        q.append(now)
        while q and now - q[0] > cfg.CIRCUIT_WINDOW_S:
            q.popleft()
        if len(q) >= cfg.CIRCUIT_ERRORS:
            self.open_until[model] = now + cfg.CIRCUIT_OPEN_S
            q.clear()
            log.warning("circuit open for %s (%ss)", model, cfg.CIRCUIT_OPEN_S)

    def success(self, model: str) -> None:
        self.errors.pop(model, None)


breaker = _Breaker()


@lru_cache(maxsize=1)
def chain_client() -> genai.Client:
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            api_version="v1beta",
            # The HTTP timeout is also sent as the server deadline (minimum 10 s); our own
            # per-attempt deadline is enforced with asyncio.wait_for below.
            timeout=10_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


@dataclass
class LlmResult:
    response: types.GenerateContentResponse
    model: str
    ms: float
    attempts: list[dict[str, Any]]


def _with_thinking(config: types.GenerateContentConfig, model: str) -> types.GenerateContentConfig:
    level = cfg.CHAT_THINKING_BY_MODEL.get(model)
    c = config.model_copy()
    c.thinking_config = (
        types.ThinkingConfig(thinking_level=types.ThinkingLevel(level)) if level else None
    )
    return c


async def generate(
    contents: list[types.Content],
    config: types.GenerateContentConfig,
    *,
    chain: tuple[str, ...] = cfg.CHAT_MODEL_CHAIN,
    deadline_s: float = cfg.CHAT_ATTEMPT_DEADLINE_S,
) -> LlmResult:
    attempts: list[dict[str, Any]] = []
    client = chain_client()
    for model in chain:
        now = time.monotonic()
        if not breaker.available(model, now):
            attempts.append({"model": model, "skipped": "circuit_open"})
            continue
        t0 = time.perf_counter()
        try:
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model, contents=contents, config=_with_thinking(config, model)
                ),
                timeout=deadline_s,
            )
        except TimeoutError:
            breaker.failure(model, time.monotonic())
            attempts.append(
                {
                    "model": model,
                    "error": "deadline",
                    "ms": round((time.perf_counter() - t0) * 1000),
                }
            )
            continue
        except genai_errors.APIError as exc:
            if exc.code in FAILOVER_CODES:
                breaker.failure(model, time.monotonic())
                attempts.append(
                    {
                        "model": model,
                        "error": exc.code,
                        "ms": round((time.perf_counter() - t0) * 1000),
                    }
                )
                continue
            log.warning("llm %s error %s: %s", model, exc.code, scrub(str(exc))[:200])
            raise
        ms = (time.perf_counter() - t0) * 1000
        breaker.success(model)
        attempts.append({"model": model, "ok": True, "ms": round(ms)})
        return LlmResult(resp, model, ms, attempts)
    raise AllModelsFailed(f"no model answered: {attempts}")

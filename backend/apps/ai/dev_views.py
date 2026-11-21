"""DEBUG-only endpoints for the M0 voice spike (/dev/voice).

Replaced in M3/M4 by the authenticated `/api/live/session` and `/api/tools/<name>`.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from apps.telemetry import timing

from . import spike, uz_format
from .gemini import GeminiNotConfigured, scrub
from .live import ToolBehavior, live_config, mint_token
from .prompts import live_system_instruction

log = logging.getLogger(__name__)


def _debug_only() -> None:
    if not settings.DEBUG:
        raise Http404


def _json_body(request: HttpRequest) -> dict[str, Any]:
    if not request.body:
        return {}
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValueError("JSON object expected")
    return data


@require_POST
def dev_live_session(request: HttpRequest) -> JsonResponse:
    _debug_only()
    try:
        body = _json_body(request)
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)
    behavior: ToolBehavior = (
        "non_blocking" if body.get("behavior") == "non_blocking" else "blocking"
    )
    instruction = live_system_instruction(
        business_name=spike.SPIKE_BUSINESS,
        today_long=uz_format.format_date_long(spike.SPIKE_TODAY),
        context_lines=spike.context_lines(),
    )
    config = live_config(
        system_instruction=instruction,
        tool_specs=[spike.EVALUATE_PURCHASE_SPEC],
        behavior=behavior,
    )
    try:
        with timing.measure("llm"):
            tok = mint_token(config)
    except GeminiNotConfigured:
        return JsonResponse({"ok": False, "error": "gemini_not_configured"}, status=503)
    except Exception as exc:
        log.warning("live token mint failed: %s", scrub(str(exc))[:300])
        return JsonResponse({"ok": False, "error": "token_failed"}, status=502)
    return JsonResponse(
        {
            "ok": True,
            "token": tok.token,
            "model": tok.model,
            "expires_at": tok.expires_at.isoformat(),
            "new_session_expires_at": tok.new_session_expires_at.isoformat(),
            "behavior": behavior,
            "mint_ms": round(tok.mint_ms, 1),
        }
    )


@require_POST
def dev_tool(request: HttpRequest, name: str) -> JsonResponse:
    _debug_only()
    if name != "evaluate_purchase":
        return JsonResponse({"ok": False, "error": "unknown_tool"}, status=404)
    t0 = time.perf_counter()
    try:
        result = spike.evaluate_purchase(_json_body(request))
    except (ValueError, TypeError) as exc:
        return JsonResponse({"ok": False, "error": "bad_args", "detail": str(exc)}, status=400)
    timing.add("engine", (time.perf_counter() - t0) * 1000)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})

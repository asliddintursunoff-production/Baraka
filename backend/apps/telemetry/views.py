"""POST /api/telemetry: batched frontend latency measurements -> LatencyEvent."""

from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from .models import LatencyEvent

MAX_EVENTS = 200
CHANNELS = {c.value for c in LatencyEvent.Channel}


def _clean(item: Any) -> LatencyEvent | None:
    if not isinstance(item, dict):
        return None
    channel, name, ms = item.get("channel"), item.get("name"), item.get("ms")
    if channel not in CHANNELS or not isinstance(name, str) or not 0 < len(name) <= 64:
        return None
    if not isinstance(ms, int | float) or isinstance(ms, bool) or not 0 <= ms < 600_000:
        return None
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    if len(json.dumps(meta)) > 2000:
        meta = {"truncated": True}
    return LatencyEvent(channel=channel, name=name, ms=float(ms), meta=meta)


@require_POST
def telemetry(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad_json"}, status=400)
    items = data.get("events") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return JsonResponse({"ok": False, "error": "events_required"}, status=400)
    events = [e for e in (_clean(i) for i in items[:MAX_EVENTS]) if e is not None]
    LatencyEvent.objects.bulk_create(events)
    return JsonResponse({"ok": True, "saved": len(events)})

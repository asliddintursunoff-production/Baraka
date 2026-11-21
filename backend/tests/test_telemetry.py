import json

import pytest

from apps.telemetry.models import LatencyEvent


@pytest.mark.django_db
def test_telemetry_saves_valid_events_only(client):
    events = [
        {"channel": "voice", "name": "session_ready", "ms": 812.4, "meta": {"connect_ms": 500}},
        {"channel": "chat", "name": "send_to_blocks", "ms": 950},
        {"channel": "nope", "name": "x", "ms": 1},
        {"channel": "api", "name": "", "ms": 1},
        {"channel": "api", "name": "neg", "ms": -1},
        {"channel": "api", "name": "bool", "ms": True},
    ]
    r = client.post(
        "/api/telemetry", data=json.dumps({"events": events}), content_type="application/json"
    )
    assert r.json() == {"ok": True, "saved": 2}
    assert LatencyEvent.objects.count() == 2


@pytest.mark.django_db
def test_telemetry_rejects_bad_body(client):
    assert (
        client.post("/api/telemetry", data="[1]", content_type="application/json").status_code
        == 400
    )

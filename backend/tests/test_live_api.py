"""M4 backend: Live session token (context preloaded, no retrieval), prefetch, finish."""

import json
from datetime import UTC, datetime

import pytest

from apps.ai import live as live_mod
from apps.ai import live_api
from apps.ai.models import Conversation, Message
from apps.ai.tools import TOOLS
from apps.tenancy.context import tenant_context
from config import app_settings as cfg

pytestmark = pytest.mark.django_db


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def fake_mint(config):
        seen["config"] = config
        return live_mod.LiveToken(
            "auth_tokens/abc",
            cfg.AI_MODELS["live"],
            datetime(2030, 1, 1, tzinfo=UTC),
            datetime(2030, 1, 1, tzinfo=UTC),
            12.5,
        )

    monkeypatch.setattr(live_api, "mint_token", fake_mint)
    return seen


def test_session_token_with_context_and_tools(owner_client, demo, captured):
    r = owner_client.post("/api/live/session", data="{}", content_type="application/json")
    d = r.json()
    assert d["token"] == "auth_tokens/abc" and d["business_name"] == "Navro'z Kafe"
    assert d["cash"]["display"].endswith("mln so'm")
    conf = captured["config"]
    names = {f.name for f in conf.tools[0].function_declarations}
    assert names == {t.name for t in TOOLS.values() if t.voice}
    assert all(f.behavior == "BLOCKING" for f in conf.tools[0].function_declarations)
    assert conf.realtime_input_config.automatic_activity_detection.silence_duration_ms == 300
    text = conf.system_instruction
    assert "say" in text and "Navro'z Kafe" in text and "so'm" in text
    assert len(text) / 4 < cfg.LIVE_CONTEXT_MAX_TOKENS  # rough token estimate


def test_prefetch_is_a_get(owner_client, demo, captured):
    assert owner_client.get("/api/live/session/prefetch").json()["ok"] is True


def test_live_session_does_not_embed_or_search(owner_client, demo, captured, monkeypatch):
    import apps.ai.gemini as g

    monkeypatch.setattr(
        g,
        "client",
        lambda: (_ for _ in ()).throw(AssertionError("no LLM/embedding on the voice path")),
    )
    assert (
        owner_client.post(
            "/api/live/session", data="{}", content_type="application/json"
        ).status_code
        == 200
    )


def test_finish_saves_transcript(owner_client, demo, monkeypatch):
    monkeypatch.setattr(
        live_api.threading, "Thread", lambda **k: type("T", (), {"start": lambda self: None})()
    )
    body = {
        "transcript": [
            {"who": "user", "text": "25 million so'mga jihoz olsam?"},
            {"who": "ai", "text": "Yo'q, hozir olmang."},
        ],
        "blocks": [{"id": "cmp", "type": "compare_bars", "title": "x", "rows": []}],
    }
    d = owner_client.post(
        "/api/live/finish", data=json.dumps(body), content_type="application/json"
    ).json()
    assert d["saved"] == 2
    with tenant_context(demo):
        conv = Conversation.objects.get(pk=d["conversation_id"])
        assert conv.channel == "voice"
        assert Message.objects.filter(conversation=conv).count() == 2

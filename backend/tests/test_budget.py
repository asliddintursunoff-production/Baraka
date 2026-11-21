"""Budget guard: usage logging, daily/total limits -> template chat, Live refused."""

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.ai import budget, live_api, llm
from apps.ai.live import LiveToken
from apps.telemetry.models import AiUsage

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enforce_budget(monkeypatch):
    """Limits are off in production by the owner's choice; the mechanism itself stays tested."""
    from config import app_settings as cfg

    monkeypatch.setattr(cfg, "AI_BUDGET_ENFORCED", True)


@pytest.fixture(autouse=True)
def clean_usage():
    AiUsage.objects.all().delete()
    yield
    AiUsage.objects.all().delete()


def test_cost_and_profile(settings):
    assert budget.token_cost("gemini-3.5-flash-lite", 1_000_000, 1_000_000) == Decimal("0.50")
    settings.DEBUG = True
    assert budget.chat_chain() == ("gemini-3.5-flash-lite",)
    settings.DEBUG = False
    assert budget.chat_chain()[0] == "gemini-3.8-flash"


def test_generate_logs_usage_and_stops_at_limit(monkeypatch):
    calls, logged = [], []

    class FakeModels:
        async def generate_content(self, *, model, contents, config):
            calls.append(model)
            return SimpleNamespace(
                usage_metadata=SimpleNamespace(
                    prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=0
                )
            )

    monkeypatch.setattr(
        llm, "chain_client", lambda: SimpleNamespace(aio=SimpleNamespace(models=FakeModels()))
    )
    monkeypatch.setattr(
        budget,
        "record",
        lambda kind, model, **k: logged.append((kind, model, budget._usage_tokens(k["usage"]))),
    )
    monkeypatch.setattr(budget, "over_limit", lambda: None)
    from google.genai import types

    res = asyncio.run(llm.generate([], types.GenerateContentConfig()))
    assert logged == [("chat", res.model, (1000, 200))]
    monkeypatch.setattr(budget, "over_limit", lambda: "daily")
    with pytest.raises(budget.BudgetExceeded):
        asyncio.run(llm.generate([], types.GenerateContentConfig()))
    assert len(calls) == 1  # no Gemini call once over the limit
    assert isinstance(budget.BudgetExceeded("x"), llm.AllModelsFailed)  # chat -> template answer


def test_daily_limit_and_record():
    u = budget.record(
        "chat",
        "gemini-3.5-flash-lite",
        usage=SimpleNamespace(prompt_token_count=1000, candidates_token_count=200),
    )
    assert u.cost_usd == Decimal("0.000180") and budget.over_limit() is None
    AiUsage.objects.create(kind="chat", model="x", cost_usd=Decimal("0.50"))
    assert budget.over_limit() == "daily"
    with pytest.raises(budget.BudgetExceeded):
        budget.check("chat")


def test_total_limit(monkeypatch):
    from datetime import timedelta

    from django.utils import timezone

    u = AiUsage.objects.create(kind="chat", model="x", cost_usd=Decimal("4.00"))
    AiUsage.objects.filter(pk=u.pk).update(created_at=timezone.now() - timedelta(days=3))
    assert budget.over_limit() == "total"


def test_live_refused_over_budget_and_reservation_settled(owner_client, demo, monkeypatch):
    from datetime import UTC, datetime

    t = datetime(2030, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(
        live_api, "mint_token", lambda conf: LiveToken("tok", "gemini-3.8-live", t, t, 5.0)
    )
    d = owner_client.post("/api/live/session").json()
    u = AiUsage.objects.get(pk=d["usage_id"])
    assert u.kind == "live" and u.seconds == 60
    owner_client.post(
        "/api/live/finish",
        data={"seconds": 18, "usage_id": u.pk, "transcript": []},
        content_type="application/json",
    )
    u.refresh_from_db()
    assert u.seconds == 18 and u.cost_usd == Decimal("0.007500")
    AiUsage.objects.create(kind="chat", model="x", cost_usd=Decimal("1.00"))
    r = owner_client.post("/api/live/session")
    assert r.status_code == 429 and r.json()["message"] == "Bugungi ovoz limiti tugadi"

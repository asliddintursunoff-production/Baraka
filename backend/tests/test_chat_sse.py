"""M3 chat SSE with a fake LLM (tests never call Gemini). Async -> transactional DB."""

import json
import time

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import AsyncClient, Client
from google.genai import types

from apps.ai import chat as chat_mod
from apps.ai.llm import AllModelsFailed, LlmResult
from apps.insights.forecasting import _cache
from apps.tenancy.models import Business

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
async def _close_worker_connections():
    """Close the DB connection of asgiref's sync worker thread (same executor as the views)."""
    yield
    from asgiref.sync import sync_to_async
    from django.db import connections

    await sync_to_async(connections.close_all)()


@pytest.fixture(autouse=True)
def _free_chat(monkeypatch):
    """These tests cover the free-chat LLM path; demo mode is tested in test_demo_chat_*."""
    from config import app_settings as cfg

    monkeypatch.setattr(cfg, "DEMO_GOLDEN_ONLY", False)


@pytest.fixture
def aclient():
    _cache.clear()
    call_command("seed_demo", "--reset", verbosity=0)
    sync = Client()
    sync.post(
        "/api/auth/login",
        data=json.dumps({"email": "demo@demo.uz", "password": "demo12345"}),
        content_type="application/json",
    )
    c = AsyncClient()
    c.cookies = sync.cookies
    yield c
    Business.objects.filter(seed_tag="demo").delete()
    get_user_model().objects.filter(username__endswith="@demo.uz").delete()
    _cache.clear()


async def collect(client, body):
    r = await client.post(
        "/api/chat/messages", data=json.dumps(body), content_type="application/json"
    )
    assert r.status_code == 200, r.content
    raw = b"".join([chunk async for chunk in r.streaming_content]).decode()
    events = []
    for frame in raw.strip().split("\n\n"):
        name = frame.split("\n")[0].removeprefix("event: ")
        data = json.loads(frame.split("\n", 1)[1].removeprefix("data: "))
        events.append((name, data))
    return events


def fake_response(*parts):
    return LlmResult(
        types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
        ),
        "fake-model",
        5.0,
        [],
    )


async def test_chip_fast_path_never_calls_llm(aclient, monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("LLM must not be called for chips")

    monkeypatch.setattr(chat_mod, "generate", boom)
    t0 = time.perf_counter()
    events = await collect(aclient, {"chip": "cash"})
    names = [e[0] for e in events]
    assert names == ["meta", "status", "blocks", "answer", "done"]
    answer = dict(events)["answer"]
    assert answer["model"] == "template" and answer["headline"].startswith("Hozir kassada")
    assert (time.perf_counter() - t0) * 1000 < 1500


async def test_purchase_question_speculative_then_llm(aclient, monkeypatch):
    calls = []

    async def fake_generate(contents, config, **kw):
        calls.append(1)
        if len(calls) == 1:
            return fake_response(
                types.Part(
                    function_call=types.FunctionCall(
                        id="c1", name="evaluate_purchase", args={"amount": 25000000}
                    )
                )
            )
        return fake_response(
            types.Part(
                text=json.dumps(
                    {
                        "verdict": "no",
                        "headline": "Yo'q, hozir olmang.",
                        "reason": "Hozir 25 million sarflasangiz, oylikka pul yetmaydi.",
                        "steps": ["Xaridni keyinroq qiling."],
                        "chips": [],
                    }
                )
            )
        )

    monkeypatch.setattr(chat_mod, "generate", fake_generate)
    events = await collect(aclient, {"text": "25 million so'mga jihoz olsam, oylikka yetadimi?"})
    names = [e[0] for e in events]
    assert names.index("blocks") < names.index("answer")
    first_blocks = next(d for n, d in events if n == "blocks")
    assert first_blocks.get("speculative") is True
    answer = dict(events)["answer"]
    assert answer["model"] == "fake-model" and answer["headline"] == "Yo'q, hozir olmang."
    assert answer["plan"]["status"] == "proposed" and answer["blocks"]
    assert names.count("blocks") == 1  # LLM asked for the same args -> speculative result reused


async def test_number_guard_falls_back_to_template(aclient, monkeypatch):
    async def lying(contents, config, **kw):
        if not any(
            getattr(p, "function_response", None) for c in contents for p in (c.parts or [])
        ):
            return fake_response(
                types.Part(
                    function_call=types.FunctionCall(
                        id="c1", name="evaluate_purchase", args={"amount": 25000000}
                    )
                )
            )
        return fake_response(
            types.Part(
                text=json.dumps(
                    {
                        "verdict": "no",
                        "headline": "Yo'q.",
                        "reason": "Sizga 99,9 mln yetmaydi.",
                        "steps": [],
                    }
                )
            )
        )

    monkeypatch.setattr(chat_mod, "generate", lying)
    answer = dict(
        await collect(aclient, {"text": "Yigirma besh million so'mga jihoz olsam bo'ladimi?"})
    )["answer"]
    assert answer["model"] == "template"
    assert "99,9" not in json.dumps(answer, ensure_ascii=False)
    assert answer["headline"] == "Yo'q, hozir olmang."


async def test_llm_down_uses_template_or_error(aclient, monkeypatch):
    async def down(*a, **k):
        raise AllModelsFailed("all busy")

    monkeypatch.setattr(chat_mod, "generate", down)
    ev = dict(await collect(aclient, {"text": "10 millionga remont qilsam bo'ladimi?"}))
    assert ev["answer"]["model"] == "template"  # speculative engine result still answers
    ev = dict(await collect(aclient, {"text": "Salom, ishlar qalay?"}))
    assert "error" in ev


async def test_demo_chat_other_question_fixed_reply_no_llm(aclient, monkeypatch):
    from config import app_settings as cfg

    monkeypatch.setattr(cfg, "DEMO_GOLDEN_ONLY", True)

    async def boom(*a, **k):
        raise AssertionError("LLM must not be called in demo mode")

    monkeypatch.setattr("apps.ai.chat.generate", boom)
    events = await collect(aclient, {"text": "salom"})
    ans = dict(events)["answer"]
    assert ans["demo"]["kind"] == "greeting" and len(ans["demo"]["cards"]) == 4
    assert ans["markdown"].startswith("Assalomu alaykum!")


async def test_demo_chat_non_golden_question_uses_normal_pipeline(aclient, monkeypatch):
    """Owner 2026-11-22: outside Q1–Q4 the AI answers from the data (not the fixed reply)."""
    from config import app_settings as cfg

    monkeypatch.setattr(cfg, "DEMO_GOLDEN_ONLY", True)
    called = []

    async def fake(*a, **k):
        from apps.ai.llm import AllModelsFailed

        called.append(1)
        raise AllModelsFailed("stop")

    monkeypatch.setattr("apps.ai.chat.generate", fake)
    events = await collect(aclient, {"text": "Ertaga ob-havo qanday bo'ladi?"})
    ans = dict(events).get("answer") or {}
    assert called and not ans.get("demo")

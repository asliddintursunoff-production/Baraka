"""M0 voice spike endpoints (DEBUG only) and the fake tool envelope."""

import json

import pytest
from django.conf import settings as dj_settings

from apps.ai import spike
from apps.ai.live import live_config
from config import app_settings as cfg


def test_fake_tool_envelope_shape_and_size():
    r = spike.evaluate_purchase({"amount": 25_000_000})
    assert set(r) == {
        "ok",
        "verdict",
        "facts",
        "display",
        "speech",
        "ui_blocks",
        "proposed_plan",
        "insufficient_data",
    }
    assert r["verdict"] == "no"
    assert r["display"]["lowest_balance"] == "−6,2 mln"
    assert r["speech"]["lowest_balance"] == "minus olti million ikki yuz ming so'm"
    assert r["speech"]["recommended_date"] == "o'n ikkinchi yanvar"
    assert {b["type"] for b in r["ui_blocks"]} == {"verdict", "compare_bars", "steps"}
    assert spike.response_size(r) <= cfg.TOOL_RESPONSE_MAX_BYTES


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"amount": 0},
        {"amount": -5},
        {"amount": "25"},
        {"amount": True},
        {"amount": 1, "installments": 40},
    ],
)
def test_fake_tool_validates_args(args):
    with pytest.raises(ValueError):
        spike.validate_args(args)


def test_model_payload_drops_ui_blocks():
    assert "ui_blocks" not in spike.evaluate_payload_for_model({"amount": 25_000_000})


@pytest.mark.django_db
def test_dev_tool_endpoint(client, debug_on):
    r = client.post(
        "/api/dev/tools/evaluate_purchase",
        data=json.dumps({"amount": 25_000_000}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json()["verdict"] == "no"
    assert "engine;dur=" in r["Server-Timing"]
    bad = client.post(
        "/api/dev/tools/evaluate_purchase",
        data=json.dumps({"amount": "x"}),
        content_type="application/json",
    )
    assert bad.status_code == 400
    assert (
        client.post("/api/dev/tools/nope", data="{}", content_type="application/json").status_code
        == 404
    )


@pytest.mark.django_db
def test_dev_endpoints_hidden_without_debug(client, settings):
    settings.DEBUG = False
    r = client.post("/api/dev/tools/evaluate_purchase", data="{}", content_type="application/json")
    assert r.status_code == 404
    r = client.post("/api/dev/live/session", data="{}", content_type="application/json")
    assert r.status_code == 404


def test_live_config_locks_expected_fields():
    conf = live_config(
        system_instruction="x", tool_specs=[spike.EVALUATE_PURCHASE_SPEC], behavior="blocking"
    )
    assert conf.response_modalities == ["AUDIO"]
    assert conf.thinking_config is None  # not configurable on gemini-3.8-live
    assert conf.proactivity is None and conf.enable_affective_dialog is None
    decl = conf.tools[0].function_declarations[0]
    assert decl.name == "evaluate_purchase" and decl.behavior == "BLOCKING"
    nb = live_config(
        system_instruction="x", tool_specs=[spike.EVALUATE_PURCHASE_SPEC], behavior="non_blocking"
    )
    assert nb.tools[0].function_declarations[0].behavior == "NON_BLOCKING"
    assert conf.session_resumption is None  # left unlocked so the client can resume


def test_api_key_never_in_live_config():
    conf = live_config(system_instruction="x", tool_specs=[spike.EVALUATE_PURCHASE_SPEC])
    if dj_settings.GEMINI_API_KEY:
        assert dj_settings.GEMINI_API_KEY not in conf.model_dump_json()


def test_answer_variant_sentence_uses_uz_format_words():
    payload = spike.evaluate_payload_for_model({"amount": 25_000_000}, with_answer=True)
    answer = payload["speech"]["answer"]
    assert answer.startswith("Yo'q, hozir olmang.")
    assert "olti million ikki yuz ming so'm" in answer
    assert "o'ninchi dekabrda" in answer and "o'n ikkinchi yanvarda" in answer
    inst = spike.evaluate_payload_for_model(
        {"amount": 25_000_000, "installments": 3}, with_answer=True
    )
    assert "to'qqiz million sakkiz yuz ming so'm" in inst["speech"]["answer"]
    assert "answer" not in spike.evaluate_payload_for_model({"amount": 1})["speech"]

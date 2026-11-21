"""M3: tool endpoint, plans, learning, chat SSE (fake LLM — tests never call Gemini)."""

import json

import pytest

from apps.actions.models import ActionPlan
from apps.ai.tools import for_model
from apps.insights.forecasting import get_forecast
from apps.knowledge.models import BusinessRule
from apps.tenancy.context import tenant_context

pytestmark = pytest.mark.django_db


def post(c, url, data):
    return c.post(url, data=json.dumps(data), content_type="application/json")


def test_tool_evaluate_purchase(owner_client, demo):
    r = post(owner_client, "/api/tools/evaluate_purchase", {"amount": 25_000_000})
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {
        "ok",
        "verdict",
        "facts",
        "display",
        "speech",
        "say",
        "ui_blocks",
        "proposed_plan",
        "insufficient_data",
    }
    assert d["verdict"] == "no"
    assert d["speech"]["recommended_date"].endswith(("yanvar", "dekabr", "fevral", "mart"))
    assert any(b["type"] == "compare_bars" for b in d["ui_blocks"])
    assert d["proposed_plan"]["status"] == "proposed"
    assert len(json.dumps(for_model(d), ensure_ascii=False).encode()) <= 2048
    assert "say" in d and d["say"].startswith("Yo'q, hozir olmang.")


def test_tool_args_are_validated(owner_client, demo):
    assert (
        post(
            owner_client, "/api/tools/evaluate_purchase", {"amount": 25_000_000, "business_id": 1}
        ).status_code
        == 400
    )
    assert post(owner_client, "/api/tools/evaluate_purchase", {"amount": "abc"}).status_code == 400
    assert post(owner_client, "/api/tools/get_forecast", {"horizon_days": 45}).status_code == 400
    assert post(owner_client, "/api/tools/nope", {}).status_code == 404


def test_tool_endpoint_server_time(owner_client, demo):
    post(owner_client, "/api/tools/evaluate_purchase", {"amount": 25_000_000})
    times = []
    for _ in range(15):
        r = post(owner_client, "/api/tools/simulate_change", {"kind": "revenue_pct", "value": -20})
        total = next(x for x in r["Server-Timing"].split(", ") if x.startswith("total"))
        times.append(float(total.split("=")[1]))
    times.sort()
    assert times[len(times) // 2] < 60, times  # spec §6: <= 60 ms p50


def test_confirm_plan_needs_explicit_yes(owner_client, demo):
    plan_id = post(owner_client, "/api/tools/evaluate_purchase", {"amount": 25_000_000}).json()[
        "proposed_plan"
    ]["id"]
    r = post(
        owner_client,
        "/api/tools/confirm_plan",
        {"plan_id": plan_id, "_user_utterance": "o'ylab ko'raman"},
    )
    assert r.json()["ok"] is False
    r = post(
        owner_client,
        "/api/tools/confirm_plan",
        {"plan_id": plan_id, "_user_utterance": "Ha, shunday qiling"},
    )
    assert r.json()["facts"]["status"] == "approved"
    with tenant_context(demo):
        assert ActionPlan.objects.filter(kind="reminder", payload__plan_id=plan_id).count() == 1
    # idempotent UI approval
    r1 = post(owner_client, f"/api/actions/{plan_id}/approve", {})
    r2 = post(owner_client, f"/api/actions/{plan_id}/approve", {})
    assert r1.json()["status"] == r2.json()["status"] == "approved"
    with tenant_context(demo):
        assert ActionPlan.objects.filter(kind="reminder", payload__plan_id=plan_id).count() == 1


def test_correction_becomes_rule_and_changes_forecast(owner_client, demo):
    before = get_forecast(demo).result
    r = post(
        owner_client,
        "/api/tools/remember_fact",
        {"text": "Agro Go'shtga to'lovni har doim 15 kun kechiktirib to'laymiz"},
    )
    cand = r.json()["candidate"]
    assert "15 kun keyin" in cand["text"] and cand["example"].startswith("Masalan,")
    r = post(owner_client, f"/api/knowledge/candidates/{cand['id']}/accept", {})
    assert r.json()["forecast_changed"]
    with tenant_context(demo):
        assert BusinessRule.objects.filter(type="payment_shift").exists()
    after = get_forecast(demo).result
    supplier_day = next(p.due_date for p in before.obligations if p.category == "supplier")
    assert after.close_on(supplier_day) > before.close_on(supplier_day)
    # cleanup for other tests in the module
    with tenant_context(demo):
        BusinessRule.objects.filter(type="payment_shift").delete()
    from apps.insights.forecasting import refresh_forecast

    refresh_forecast(demo)


def test_bootstrap(owner_client, demo):
    d = owner_client.get("/api/chat/bootstrap").json()
    assert d["brief"]["time"] == "08:00" and d["chips"][0]["id"] == "cash"
    assert d["basis"]["confidence"]["label"] in {"Yuqori", "O'rtacha", "Past"}

"""Catalogue batch 2 (cash & forecast) on Lazzat + shared facts identical to Q1–Q4."""

import pytest

from apps.ai.catalog import registry
from apps.ai.cfo_router import route
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
BATCH = ["S18", "N01", "N02", "N03", "N42", "N43", "N53", "N57"]


@pytest.fixture(scope="module")
def lazzat(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        b, _ = connect(load("lazzat"), "Lazzat Lavash (cat2)")
        yield b


@pytest.mark.parametrize("cid", BATCH)
def test_intent_routes_and_renders(lazzat, cid):
    it = registry()[cid]
    with tenant_context(lazzat):
        for q in it.phrases:
            assert route(q)[0] == ("catalog", {"intent": it.intent}), q
        r = run_tool(
            ToolContext(lazzat, 0, "chat", last_user_text=it.title),
            "catalog",
            {"intent": it.intent},
        )
    rep = r["ui_blocks"][0]
    assert (
        rep["type"] == "report"
        and rep["variant"] == "catalog"
        and len(rep["kpis"]) == 3
        and rep["source"]
    )
    assert r["speech_segments"][0]["text"] and "jadvalingizda yo'q" not in r["md"]


def test_shared_facts_match_golden(lazzat):
    with tenant_context(lazzat):
        s18 = run_tool(ToolContext(lazzat, 0, "chat"), "catalog", {"intent": "cash_risk_3m"})
        n03 = run_tool(
            ToolContext(lazzat, 0, "chat"), "catalog", {"intent": "loan_payment_coverage"}
        )
        n02 = run_tool(ToolContext(lazzat, 0, "chat"), "catalog", {"intent": "payroll_coverage"})
    # Q3 spec: "5-dekabr (oylik kuni) kassa: 44,7 mln"
    assert s18["facts"]["min_date"] == "2026-12-05" and s18["facts"]["min_balance"] == "44,7 mln"
    assert n02["facts"]["after"] == "44,7 mln"
    assert (
        n03["facts"]["balance"] == "110,0 mln"
    )  # Kontragentlar: Bank krediti (payables report uses the same)


def test_safe_to_spend_amount_param(lazzat):
    with tenant_context(lazzat):
        r = run_tool(
            ToolContext(lazzat, 0, "chat"),
            "catalog",
            {"intent": "safe_to_spend", "amount": 30_000_000},
        )
    assert "chegaradan pastga" in r["md"]

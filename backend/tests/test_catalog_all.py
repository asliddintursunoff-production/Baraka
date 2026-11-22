"""Every implemented catalogue intent: all its phrasings route to it, and it renders a real card on Lazzat."""

import pytest

from apps.ai import catalog_tools  # noqa: F401  (registers intents)
from apps.ai.catalog import IMPLEMENTED, registry
from apps.ai.cfo_router import route
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
DONE = sorted(i.id for i in registry().values() if i.intent in IMPLEMENTED)


@pytest.fixture(scope="module")
def lazzat(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        b, _ = connect(load("lazzat"), "Lazzat Lavash (cat-all)")
        yield b


@pytest.mark.parametrize("cid", DONE)
def test_catalog_intent(lazzat, cid):
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
        and len(rep["kpis"]) >= 3
        and rep["source"]
        and r["speech_segments"][0]["text"]
    )
    assert "−100" not in r["md"] and "jadvalingizda yo'q" not in r["md"]

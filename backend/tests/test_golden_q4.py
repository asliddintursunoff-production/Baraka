"""Golden Q4 (revenue_growth_plan) on Lazzat: spec values on the spec's file, side answers, params."""

import pytest

from apps.ai.golden_tools import match
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
Q = "Korxona daromadini 10 foizga qisqa muddatda oshirish uchun strategiya tuzib ber."


@pytest.fixture
def lazzat():
    b, _ = connect(load("lazzat"), "Lazzat Lavash")
    return b


def test_q4_report(lazzat):
    with tenant_context(lazzat):
        r = run_tool(ToolContext(lazzat, 0, "chat", last_user_text=Q), "revenue_growth_plan", {})
    rep = r["ui_blocks"][0]
    assert [k["value"] for k in rep["kpis"]] == ["171,8 mln", "6 hafta", "+8 000 000", "~4,4 mln"]
    lev = next(sec for sec in rep["sections"] if sec["id"] == "levers")["table"]["rows"]
    assert lev[-1][3] == "**+15 550 000 (+10,0%)**" and lev[-1][4] == "**+7 980 000**"
    wf = rep["sections"][0]["chart"]
    assert wf["start"]["value"] == 156.2 and [x["value"] for x in wf["steps"]] == [
        1.07,
        0.62,
        3.93,
        3.93,
        6.0,
    ]
    assert [x["cue"] for x in r["speech_segments"]] == [
        "verdict+kpi",
        "waterfall",
        "evidence",
        "plan_chart",
        "approve_button",
    ]


@pytest.mark.parametrize(
    "q",
    [
        "Daromadimni tezda 10% ga qanday oshiraman?",
        "Savdoni qanday ko'paytirsam bo'ladi?",
        "O'rtacha chekni qanday oshiraman?",
    ],
)
def test_q4_paraphrases(q):
    assert match(q)[0].id == "revenue_growth_plan"


def test_q4_side_and_params(lazzat):
    assert match("Daromadni 20% ga oshirish mumkinmi?")[1] == {"target": 20}
    with tenant_context(lazzat):
        ctx = ToolContext(lazzat, 0, "chat", last_user_text="Reklamasiz qilsa bo'ladimi?")
        side = run_tool(ctx, "revenue_growth_plan", {})
        assert "+9,55 mln (+6,1%)" in side["md"]
        ctx20 = ToolContext(lazzat, 0, "chat", last_user_text="20% kerak bo'lsa?")
        assert "+31 mln kerak" in run_tool(ctx20, "revenue_growth_plan", {"target": 20})["md"]

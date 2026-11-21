"""Golden Q3 (equipment_investment) on Lazzat: spec values, paraphrases, side answers, other equipment."""

import pytest

from apps.ai.golden_tools import _annuity, match
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
Q = "25 millionga lavash apparat olmoqchiman — bu investitsiya bo'ladimi yoki zarariga ishlaydimi?"


@pytest.fixture
def lazzat():
    b, _ = connect(load("lazzat"), "Lazzat Lavash")
    return b


def test_q3_report(lazzat):
    m = match(Q)
    assert m[0].id == "equipment_investment" and m[1] == {
        "equipment": "lavash apparati",
        "price": 25_000_000,
    }
    with tenant_context(lazzat):
        r = run_tool(ToolContext(lazzat, 0, "chat", last_user_text=Q), "equipment_investment", m[1])
    rep = r["ui_blocks"][0]
    assert [k["value"] for k in rep["kpis"]] == ["−430 000", "May 2027", "+4 320 000", "~5,8 oy"]
    fin = next(x for x in rep["sections"] if x["id"] == "financing")["table"]["rows"]
    assert fin[1][2] == "3 667 000" and fin[2][2] == "2 364 000" and fin[2][4] == "3 370 000"
    jc = next(x for x in rep["sections"] if x["id"] == "jcurve")["chart"]["series"]
    assert jc[0]["data"][-1] == 7.39 and jc[1]["data"][-1] == 9.54
    assert [x["cue"] for x in r["speech_segments"]] == [
        "verdict+kpi",
        "capacity_chart",
        "may_table",
        "jcurve",
        "financing",
        "approve_button",
    ]


@pytest.mark.parametrize(
    "q",
    [
        "Yangi lavash apparati olsam arziydimi?",
        "Apparat olsam necha oyda o'zini qoplaydi?",
        "Apparatni kreditga olsam-chi?",
    ],
)
def test_q3_paraphrases(q):
    assert match(q)[0].id == "equipment_investment"


def test_q3_side_and_param(lazzat):
    assert round(_annuity(25_000_000, __import__("decimal").Decimal("0.24"), 12)) == 2_363_990
    with tenant_context(lazzat):
        side = run_tool(
            ToolContext(lazzat, 0, "chat", last_user_text="Eski apparat buzildi, majburman"),
            "equipment_investment",
            {"price": 25_000_000, "reason": "almashtirish"},
        )
        assert side["md"].startswith("**Darhol oling.**")
        fr = run_tool(
            ToolContext(lazzat, 0, "chat", last_user_text="30 mln ga fritur olsam?"),
            "equipment_investment",
            {"price": 30_000_000, "equipment": "fritur"},
        )
        assert not fr.get("pinned") and fr["ui_blocks"][0]["type"] == "report"

"""Golden Q1 (channel_economics) on Lazzat_Lavash_FastFood_2026.xlsx — numbers from the spec."""

from decimal import Decimal as D

import pytest

from apps.ai.cfo_router import route
from apps.ai.golden_tools import match
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
SPEC_ORDERS = {"Uzum": 174, "Yandex": 257, "O'z": 189}


@pytest.fixture
def lazzat():
    b, _ = connect(load("lazzat"), "Lazzat Lavash")
    return b


def _q1(b, **args):
    from apps.engine import channels as C
    from apps.integrations.models import DataSource

    with tenant_context(b):
        s = DataSource.objects.exclude(summary={}).first().summary
    return C.compute(s, C.Params(orders={k: D(v) for k, v in SPEC_ORDERS.items()}, **args))


def test_q1_numbers(lazzat):
    e = _q1(lazzat)
    keep = {c.name: c.keep100k for c in e.channels}
    assert abs(keep["Uzum Tezkor"] - 49420) < 20
    assert abs(keep["Yandex Eats"] - 48300) < 20
    assert abs(keep["O'z dostavka"] - 43060) < 20
    assert abs(e.own_plan.keep100k - 49940) < 30
    sc = {s.key: s.delta for s in e.scenarios}
    assert abs(sc["exit"] + 20_070_000) < 20_000
    assert abs(sc["shift"] - 990_000) < 10_000
    assert abs(sc["markup"] - 1_460_000) < 10_000
    assert abs(sc["both"] - 2_010_000) < 10_000
    assert int(e.orders_now) == 189 and int(e.orders_plan) == 318
    assert round(float(e.load_now), 2) == 0.42 and round(float(e.load_plan), 2) == 0.71
    assert abs(sum(e.receivables.values(), D(0)) - 33_300_000) < 50_000
    assert e.month == "2026-10-01"


def test_q1_tool_report_and_speech(lazzat):
    with tenant_context(lazzat):
        r = run_tool(ToolContext(lazzat, 0, "chat"), "channel_economics", {})
    rep = r["ui_blocks"][0]
    assert rep["type"] == "report" and len(rep["kpis"]) == 4
    assert [s["id"] for s in rep["sections"]][:2] == ["chart_100k", "table_100k"]
    cues = [s["cue"] for s in r["speech_segments"]]
    assert cues[0] == "verdict+kpi" and cues[-1] == "approve_button"
    assert r["proposed_plan"]["status"] == "proposed"


@pytest.mark.parametrize(
    "q",
    [
        "Yandex va Uzum menga foydalimi yoki o'z dostavkamni kuchaytiraymi?",
        "Agregatorlar foydalimi?",
        "Qaysi savdo kanali eng foydali?",
        "Uzum komissiyasi meni yeb qo'yyaptimi?",
    ],
)
def test_q1_paraphrases(q):
    m = match(q)
    assert m is not None and m[0].id == "channel_economics"


def test_q1_param_variant(lazzat):
    m = match("Uzum'dan chiqsam nima bo'ladi?")
    assert m and m[1] == {"exit": "uzum"}
    assert match("50% ini o'tkazsam-chi?", "channel_economics")[1] == {"shift_pct": 50}
    e = _q1(lazzat, shift_pct=D("0.5"))
    assert e.orders_plan > 318
    with tenant_context(lazzat):
        assert route("2-kuryer olsam?")[0] == ("channel_economics", {"couriers": 2})

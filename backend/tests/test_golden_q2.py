"""Golden Q2 (hire_payback) + Q1 side questions on Lazzat_Lavash_FastFood_2026.xlsx."""

from decimal import Decimal as D

import pytest

from apps.ai.golden_tools import is_side_question, match
from apps.ai.tools import ToolContext, run_tool
from apps.engine import channels as C
from apps.engine import hiring as H
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
ORD = {"Uzum": D(174), "Yandex": D(257), "O'z": D(189)}


@pytest.fixture
def summ():
    from apps.integrations.models import DataSource

    b, _ = connect(load("lazzat"), "Lazzat Lavash")
    with tenant_context(b):
        return b, DataSource.objects.exclude(summary={}).first().summary


def test_q2_numbers(summ):
    _, s = summ
    h = H.compute(s, H.Params(courier_orders=D(189)))
    assert abs(h.cost - 2_288_000) < 2_000
    assert abs(h.gain_gp - 1_655_000) < 2_000
    assert abs(h.net + 633_000) < 2_000 and h.payback_months is None
    assert abs(h.cumulative[0] / 1_000_000 - D("-1.76")) < D("0.02")
    assert abs(h.cumulative[-1] / 1_000_000 - D("-8.72")) < D("0.02")
    assert abs(h.alt_net - 2_655_000) < 5_000 and abs(
        h.alt_cumulative[-1] / 1_000_000 - D("30.55")
    ) < D("0.1")
    assert (
        abs(h.breakeven_uplift - D("0.055")) < D("0.001")
        and abs(h.breakeven_hall_rev - 81_000_000) < 100_000
    )
    assert h.months_to_breakeven == 15
    assert abs(h.sat_checks - D("75.6")) < D("0.1") and round(float(h.sat_checks / 90), 2) == 0.84
    assert abs(h.peak_checks - D("9.8")) < D("0.1")
    assert h.lost_days_recent == 0 and h.hire_month == "May 2027"
    assert h.months_labels[0] == "Dek" and h.meal_dish == "Lavash tovuqli"


def test_q2_tool_and_paraphrases(summ):
    b, _ = summ
    with tenant_context(b):
        r = run_tool(ToolContext(b, 0, "chat"), "hire_payback", {"role": "ofitsiant"})
    rep = r["ui_blocks"][0]
    assert rep["type"] == "report" and rep["kpis"][1]["value"] == "Qoplamaydi"
    assert [x["cue"] for x in r["speech_segments"]] == [
        "verdict+kpi",
        "load",
        "chart_cumulative",
        "signals",
        "approve_button",
    ]
    for q in (
        "Yana bitta ofitsam olsam, o'zini oqlaydimi?",
        "Yangi ishchi olsam arziydimi?",
        "Kassir qo'shsam foyda bo'ladimi?",
    ):
        assert match(q)[0].id == "hire_payback"
    assert match("3 millionlik ishchi olsam necha oyda qaytadi?")[1] == {"salary": 3_000_000}
    assert (
        H.compute(
            _[1] if False else summ[1], H.Params(salary=D(1_500_000), courier_orders=D(189))
        ).net
        > -633_000
    )


def test_q1_side_answers(summ):
    _, s = summ

    def sc(**kw):
        return {x.key: x.delta for x in C.compute(s, C.Params(orders=ORD, **kw)).scenarios}

    assert abs(sc(shift_pct=D("0.5"))["both"] - 2_370_000) < 10_000
    assert abs(sc(shift_pct=D("0.5"), couriers=2)["both"] + 130_000) < 10_000
    assert abs(sc(couriers=2)["both"] + 490_000) < 10_000
    assert abs(sc(markup_pct=D(0), markup_drop_pct=D(0))["both"] - 990_000) < 10_000
    assert abs(sc(markup_pct=D("0.05"), markup_drop_pct=D("0.03"))["both"] - 1_670_000) < 10_000
    assert abs(sc(exit_only="uzum")["exit_one"] + 4_650_000) < 10_000
    assert is_side_question("Nega Uzum Yandex'dan foydaliroq?") and is_side_question(
        "Bu raqamlar qanday chiqdi?"
    )
    assert match("Narxni oshirmasam, faqat mijozni o'tkazsam?", "channel_economics")[1] == {
        "markup_pct": 0
    }

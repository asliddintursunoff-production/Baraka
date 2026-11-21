"""Answer policy regressions (Lazzat): never 'jadvalda yo'q' for data that exists; compute what-ifs;
Q3 follow-ups (max price, other prices) anchored to the trigger month. Chat + Live (voice channel)."""

import pytest

from apps.ai.cfo_router import route
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
BANNED = ("jadvalingizda yo'q", "faqat biznesingiz puli")


@pytest.fixture
def lazzat():
    b, _ = connect(load("lazzat"), "Lazzat Lavash")
    return b


def ask(b, q, prev=None, channel="chat"):
    with tenant_context(b):
        name, args = route(q, prev)[0]
        r = run_tool(ToolContext(b, 0, channel, last_user_text=q), name, args)
    assert not any(x in r["md"] for x in BANNED)
    r["md"] = r["md"].replace("\xa0", " ")
    return name, r


@pytest.mark.parametrize("channel", ["chat", "voice"])
def test_a_cook_salaries(lazzat, channel):
    name, r = ask(lazzat, "Oshpazlar qancha oylik olyapti?", channel=channel)
    assert name == "lookup"
    for v in ("5 500 000", "4 100 000", "3 500 000", "3 300 000"):
        assert v in r["md"]
    assert "Oshxona yordamchisi" not in r["md"]


@pytest.mark.parametrize("channel", ["chat", "voice"])
def test_b_salary_three_times(lazzat, channel):
    name, r = ask(lazzat, "Oshpaz oyligini 3 barobar oshirmoqchiman", channel=channel)
    assert name == "salary_change" and r["md"].startswith("**Qilmang")
    f = r["facts"]
    assert f["extra"] == "34,3 mln" and f["new_net"] == "−16,6 mln" and f["runway"] == "4.3"
    assert f["alt20"] == "3,4 mln" and "14,3 mln" in r["md"]


@pytest.mark.parametrize("channel", ["chat", "voice"])
def test_c_q3_max_price(lazzat, channel):
    name, r = ask(
        lazzat,
        "Necha puldan qimmatiga olsam zarariga kirib ketaman?",
        prev="equipment_investment",
        channel=channel,
    )
    assert name == "equipment_investment"
    assert (
        r["facts"]["max24"] == "103,7 mln"
        and r["facts"]["npv"] == "175,1 mln"
        and r["facts"]["anchor"] == "May 2027"
    )


@pytest.mark.parametrize(
    ("q", "pb"), [("10 mln bo'lsa-chi?", "2.3"), ("45 mln bo'lsa-chi?", "10.4")]
)
def test_d_q3_price_variants(lazzat, q, pb):
    name, r = ask(lazzat, q, prev="equipment_investment")
    assert name == "equipment_investment" and r["facts"]["payback"] == pb
    assert "May 2027 dan keyin" in r["md"] and "−430 000" in r["md"]

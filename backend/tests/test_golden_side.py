"""Q1–Q4 follow-ups (≥ 6 each): 2 parameter changes, 2 from section 7.1 (or recomputed), 1 'nega', 1 cross-jump.
Base payloads stay frozen (test_golden_snapshots)."""

import pytest

from apps.ai.cfo_router import route
from apps.ai.golden_tools import is_side_question
from apps.ai.tools import ToolContext, run_tool
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def lazzat(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        b, _ = connect(load("lazzat"), "Lazzat Lavash (side)")
        yield b


def run(b, q, prev):
    """Mirror chat: route; an empty route (or a 'nega' follow-up) with an active golden re-runs it."""
    import json

    from apps.ai.golden_tools import INTENTS

    with tenant_context(b):
        routed = route(q, prev)
        if prev and (not routed or is_side_question(q)):
            routed = [(next(i.tool for i in INTENTS if i.id == prev), {})]
        assert routed, q
        name, args = routed[0]
        r = run_tool(ToolContext(b, 0, "chat", last_user_text=q), name, args)
    text = (r["md"] + json.dumps(r.get("ui_blocks") or [], ensure_ascii=False)).replace("\xa0", " ")
    return name, args, r, text


PARAM = [  # (active golden, question, expected tool, must contain)
    ("channel_economics", "40% ini o'tkazsam-chi?", "channel_economics", "Oldin → Yangi"),
    ("channel_economics", "Uzum'dan chiqsam nima bo'ladi?", "channel_economics", "−4,65"),
    ("hire_payback", "Oshpaz olsam-chi?", "hire_payback", "Oldin → Yangi"),
    ("hire_payback", "3 mln oylik bilan ishchi olsam?", "hire_payback", "Oldin → Yangi"),
    ("equipment_investment", "45 mln bo'lsa-chi?", "equipment_investment", "Oldin → Yangi"),
    ("equipment_investment", "80 mln bo'lsa-chi?", "equipment_investment", "Oldin → Yangi"),
    ("revenue_growth_plan", "20% kerak bo'lsa?", "revenue_growth_plan", "+31 mln kerak"),
    ("revenue_growth_plan", "Daromadni 15% ga oshirish mumkinmi?", "revenue_growth_plan", "15%"),
]
SIDE71 = [
    ("channel_economics", "Telegram-bot qilish qancha turadi?", "3–5 oyda"),
    ("channel_economics", "Yandex komissiyasini kamaytirsa bo'ladimi?", "0,48 mln"),
    ("equipment_investment", "Bo'lib to'lasam oyiga qancha?", "3 667 000"),
    ("equipment_investment", "Elektrni qancha yeydi?", "330 000"),
    ("revenue_growth_plan", "Reklamasiz qilsa bo'ladimi?", "+9,55 mln"),
    ("revenue_growth_plan", "Eng tez natija qaysi?", "+1,7 mln"),
    ("hire_payback", "Kassir olsam?", "kassir"),
    ("hire_payback", "Kuryer olsam o'zini oqlaydimi?", "kuryer"),
]
CROSS = [
    ("channel_economics", "Yana bitta ofitsiant olsam?", "hire_payback"),
    ("hire_payback", "Yandex foydalimi?", "channel_economics"),
    ("equipment_investment", "Daromadni 10% oshirish strategiyasini tuz", "revenue_growth_plan"),
    ("revenue_growth_plan", "25 millionga lavash apparat olsam?", "equipment_investment"),
]
WHY = [
    "Nega Uzum Yandex'dan foydaliroq?",
    "Nega qoplamaydi?",
    "Nega mayda olish kerak?",
    "Bu raqamlar qanday chiqdi?",
]


@pytest.mark.parametrize(("prev", "q", "tool", "must"), PARAM)
def test_param_change(lazzat, prev, q, tool, must):
    name, _a, _r, md = run(lazzat, q, prev)
    assert name == tool and must in md, md[:300]


@pytest.mark.parametrize(("prev", "q", "must"), SIDE71)
def test_side_71(lazzat, prev, q, must):
    name, _a, _r, md = run(lazzat, q, prev)
    assert name == prev and must in md.lower() if must.islower() else must in md, md[:300]


@pytest.mark.parametrize(("prev", "q", "tool"), CROSS)
def test_cross_jump(lazzat, prev, q, tool):
    with tenant_context(lazzat):
        assert route(q, prev)[0][0] == tool


@pytest.mark.parametrize("q", WHY)
def test_why_goes_to_golden_context(q):
    assert is_side_question(q)

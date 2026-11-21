"""Part C: every CFO module is a tool with facts + Uzbek markdown + a captioned card."""

import pytest

from apps.ai.tools import TOOLS, ToolContext, for_model
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
NAMES = (
    "break_even",
    "stress_test",
    "cash_sources",
    "net_position",
    "kpi_scorecard",
    "plan_vs_actual",
    "driver_decomposition",
    "debt_schedule",
)


@pytest.fixture(scope="module")
def outs(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from django.db import transaction

        with transaction.atomic():
            b, _ = connect(load("namuna"), "C tools")
            with tenant_context(b):
                ctx = ToolContext(business=b, user_id=None, channel="chat")
                res = {n: TOOLS[n].handler(ctx, {}) for n in NAMES}
            transaction.set_rollback(True)
    return res


@pytest.mark.parametrize("name", NAMES)
def test_tool_returns_markdown_facts_and_captioned_cards(outs, name):
    r = outs[name]
    assert r["ok"] and r["md"] and r["facts"], name
    for blk in r["ui_blocks"]:
        assert blk.get("caption"), (name, blk["id"])
    assert len(str(for_model(r)).encode()) < 6000


def test_key_numbers_reach_the_text(outs):
    assert "1439,5 mln" in outs["cash_sources"]["md"] and "796,7 mln" in outs["cash_sources"]["md"]
    assert "260,0 mln" in outs["net_position"]["md"]
    assert "chek" in outs["break_even"]["md"]
    assert "| −30% |" in outs["stress_test"]["md"]


def test_template_workbook_gets_a_plain_explanation(django_db_blocker):
    b, _ = connect(load("shablon"), "C empty")
    with tenant_context(b):
        ctx = ToolContext(business=b, user_id=None, channel="chat")
        r = TOOLS["break_even"].handler(ctx, {})
    assert "Foyda-zarar" in r["md"] and not r["facts"]


def test_detail_tools_name_products_dishes_losses_and_staff(outs_detail):
    r = outs_detail
    assert "Kartoshka" in r["products"]["md"] and "Mol go'shti" in r["products"]["md"]
    assert r["un"]["facts"]["product"] == "Un" and "Un" in r["un"]["md"]
    assert r["kartoshka"]["facts"]["product"] == "Kartoshka" and r["kartoshka"]["facts"]["dishes"]
    assert "Klassik burger" in r["menu"]["md"] and "Mol kotleti" in r["burger"]["md"]
    assert "kamomad" in r["losses"]["md"].lower() and r["staff"]["facts"]["staff"]
    assert any(x["name"] == "Mol go'shti" for x in r["expenses"]["facts"]["products"])


def test_find_names_handles_uzbek_endings():
    from apps.ai.detail_tools import find_names

    names = ["Un", "Kartoshka", "Mol go'shti", "Tuz"]
    assert find_names("Unga qancha pul ketdi?", names) == ["Un"]
    assert find_names("kartoshkaning narxi oshdimi", names) == ["Kartoshka"]
    assert find_names("mol go'shtiga", names) == ["Mol go'shti"]
    assert find_names("uning narxi", names) == []


@pytest.fixture(scope="module")
def outs_detail(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from django.db import transaction

        with transaction.atomic():
            b, _ = connect(load("namuna"), "Detail tools")
            with tenant_context(b):
                ctx = ToolContext(business=b, user_id=None, channel="chat")
                calls = {
                    "products": ("product_costs", {}),
                    "un": ("product_costs", {"product": "un"}),
                    "kartoshka": ("product_costs", {"product": "kartoshkaga"}),
                    "menu": ("menu_analysis", {}),
                    "burger": ("menu_analysis", {"dish": "klassik burger"}),
                    "losses": ("losses", {}),
                    "staff": ("staff_costs", {}),
                    "expenses": ("get_expenses", {}),
                }
                res = {k: TOOLS[n].handler(ctx, a) for k, (n, a) in calls.items()}
                from apps.ai.cfo_router import route

                res["routes"] = {q: route(q) for q in ROUTE_QS}
                for k in ("un", "kartoshka", "burger", "losses", "staff"):
                    print(f"\n### {k}\n{res[k]['md'][:900]}")
            transaction.set_rollback(True)
    return res


ROUTE_QS = (
    "Unga qancha pul ketdi?",
    "Kartoshka narxi oshdimi?",
    "Oktyabr xarajatlarini nomma-nom ko'rsat",
    "Biznesim qanday?",
    "Klassik burger tannarxi qancha?",
    "Savdo 30% tushsa nima bo'ladi?",
)


def test_router_sends_questions_to_the_right_modules(outs_detail):
    r = {q: [n for n, _ in v] for q, v in outs_detail["routes"].items()}
    assert outs_detail["routes"][ROUTE_QS[0]][0] == ("product_costs", {"product": "Un"})
    assert outs_detail["routes"][ROUTE_QS[1]][0] == ("product_costs", {"product": "Kartoshka"})
    assert r[ROUTE_QS[2]] == ["get_expenses", "product_costs"]
    assert {"kpi_scorecard", "cash_sources", "net_position", "plan_vs_actual"} <= set(
        r[ROUTE_QS[3]]
    )
    assert outs_detail["routes"][ROUTE_QS[4]][0] == ("menu_analysis", {"dish": "Klassik burger"})
    assert r[ROUTE_QS[5]][:2] == ["stress_test", "break_even"]


def test_markdown_answer_parsing_and_chunks():
    from apps.ai.chat import md_chunks, parse_answer

    a = parse_answer(
        "**31-oktyabr 2026 holatiga kassada 1439,5 mln.**\n\n### Nima uchun\n- a\n\nCHIPS: Un narxi? | Kredit qachon yopiladi? | Food cost"
    )
    assert a["headline"] == "31-oktyabr 2026 holatiga kassada 1439,5 mln."
    assert (
        a["chips"] == ["Un narxi?", "Kredit qachon yopiladi?", "Food cost"]
        and "CHIPS" not in a["markdown"]
    )
    assert parse_answer('{"verdict": "no", "headline": "Yo\'q", "steps": []}')["headline"] == "Yo'q"
    md = "\n\n".join(f"Paragraf {i} " + "x" * 150 for i in range(6))
    assert "".join(md_chunks(md)) == md and len(md_chunks(md)) > 1


@pytest.mark.parametrize(
    "first",
    [
        "apps.ai.chat",
        "apps.ai.cfo_router",
        "apps.ai.detail_tools",
        "apps.ai.cfo_tools",
        "config.urls",
    ],
)
def test_tool_modules_import_in_any_order(first):
    import subprocess
    import sys

    code = (
        "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); "
        f"import importlib; importlib.import_module('{first}'); from apps.ai.tools import TOOLS; "
        "assert {'product_costs', 'break_even', 'trend_watch', 'get_expenses'} <= set(TOOLS)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]

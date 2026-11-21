"""A8 golden values on the Namuna workbook: cash ledger, cash sources, P&L, plan vs actual,
KPIs, break-even, stress, balances. Exact where the file gives exact numbers."""

from decimal import Decimal

import pytest

from apps.engine import cfo
from apps.finance.models import CashAccount
from apps.tenancy.context import tenant_context
from tests.test_finmodel_golden import connect, load, no_llm  # noqa: F401

pytestmark = pytest.mark.django_db
M = Decimal(1_000_000)
OCT = "2026-10-01"


def mln(x: Decimal, q: str = "0.1") -> Decimal:
    return (Decimal(x) / M).quantize(Decimal(q))


def near(x: Decimal, expected: Decimal, pct: int) -> bool:
    return abs(Decimal(x) - expected) <= abs(expected) * Decimal(pct) / 100


@pytest.fixture(scope="module")
def s(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from django.db import transaction

        with transaction.atomic():
            b, src = connect(load("namuna"), "A8")
            with tenant_context(b):
                opening = CashAccount.objects.get().opening_balance
            out = dict(src.summary) | {"_opening": opening}
            transaction.set_rollback(True)
    return out


def test_month_end_cash_jan_to_oct(s):
    got = [mln(s["months"][f"2026-{m:02d}-01"]["cash_end"]) for m in range(1, 11)]
    assert got == [Decimal(x) for x in ("966.8", "837.2", "898.5", "983.3", "1066.9", "1168.6", "1233.6", "1321.5", "1363.3", "1439.5")]


def test_cash_sources_jan_to_oct(s):
    c = cfo.cash_sources(s, s["_opening"])
    assert mln(c.opening) == Decimal("50.0") and mln(c.operating) == Decimal("796.7")
    assert mln(c.investing) == Decimal("-558.0") and mln(c.financing) == Decimal("1151.2")
    assert (mln(c.owner_in), mln(c.loan_in), mln(c.loan_repaid), mln(c.interest)) == (
        Decimal("1000.0"), Decimal("300.0"), Decimal("-40.0"), Decimal("-58.8"))
    assert mln(c.closing) == Decimal("1439.5")


def test_october_pl_and_outflows(s):
    assert mln(cfo.pl_value(s, "sof tushum", OCT)) == Decimal("445.0")
    assert mln(cfo.pl_value(s, "sof foyda", OCT)) == Decimal("95.8")
    assert mln(cfo.pl_value(s, "ebitda", OCT)) == Decimal("131.1")
    items = {k: mln(v) for k, v in s["journals"]["outflow_items"][OCT].items()}
    assert items["Yetkazib beruvchiga to'lov"] == Decimal("162.2") and items["Ish haqi to'lovi"] == Decimal("63.4")
    assert items["Hisoblangan xarajat to'lovi"] == Decimal("27.0") and items["Soliq to'lovi"] == Decimal("25.0")
    assert items["Kredit / qarz qaytarildi"] == Decimal("10.0") and items["Kommunal xizmatlar"] == Decimal("8.7")
    assert items["Kredit foizi"] == Decimal("5.4") and items["Marketing va reklama"] == Decimal("5.0")
    assert items["Qadoqlash materiallari"] == Decimal("4.0") and items["Kunbay ishchilar"] == Decimal("3.0")
    assert items["Taksi va yetkazish"] == Decimal("3.0") and items["Xo'jalik mollari"] == Decimal("2.5")
    assert items["Bank komissiyasi"] == Decimal("2.4") and items["Internet, aloqa, POS"] == Decimal("1.5")
    total = sum(Decimal(v) for v in s["journals"]["outflow_items"][OCT].values())
    assert abs(total / M - Decimal("323.5")) <= Decimal("0.5")
    assert mln(s["months"][OCT]["transfers"]) == Decimal("152.0")


def test_weekday_average_z_report_aug_oct(s):
    wd = {int(k): mln(v, "0.01") for k, v in s["journals"]["weekday_z"].items()}
    assert [wd[i] for i in range(7)] == [Decimal(x) for x in ("11.86", "11.98", "12.57", "12.57", "15.29", "16.47", "15.10")]


def test_balances_31_oct(s):
    n = cfo.net_position(s)
    assert mln(n.loan) == Decimal("260.0")
    pay = {k: mln(v) for k, v in n.payables}
    assert pay["Yetkazib beruvchilar"] == Decimal("26.8") and pay["Soliq"] == Decimal("26.2")
    recv = {k: mln(v) for k, v in n.receivables}
    assert recv["Yandex Eats"] == Decimal("47.9") and recv["Uzum Tezkor"] == Decimal("30.2")


def test_october_vs_plan(s):
    p = {x.key: x for x in cfo.plan_vs_actual(s, OCT).lines}
    assert p["cheklar soni"].fact == 4184 and p["cheklar soni"].plan.quantize(Decimal("0.1")) == Decimal("4590.7")
    assert (p["cheklar soni"].diff_pct * 100).quantize(Decimal("0.1")) == Decimal("-8.9")
    assert p["o'rtacha chek"].fact.quantize(Decimal(1)) == 106346 and p["o'rtacha chek"].plan == 85000
    assert (p["o'rtacha chek"].diff_pct * 100).quantize(Decimal("0.1")) == Decimal("25.1")
    assert (p["sof tushum"].diff_pct * 100).quantize(Decimal("0.1")) == Decimal("14.0")
    assert (mln(p["mahsulot tannarxi"].fact), mln(p["mahsulot tannarxi"].plan)) == (Decimal("161.1"), Decimal("124.9"))
    assert (p["mahsulot tannarxi"].diff_pct * 100).quantize(Decimal(1)) == 29
    assert (mln(p["agregator komissiyasi"].fact), mln(p["agregator komissiyasi"].plan)) == (Decimal("18.6"), Decimal("15.6"))
    assert (mln(p["sof foyda"].fact), mln(p["sof foyda"].plan)) == (Decimal("95.8"), Decimal("78.8"))
    assert (cfo.plan_vs_actual(s, OCT).ytd_checks_pct * 100).quantize(Decimal("0.1")) == Decimal("-10.9")


def test_october_kpis(s):
    k = {x.key: x for x in cfo.kpi_scorecard(s, OCT).kpis}
    assert (k["food"].value * 100).quantize(Decimal("0.1")) == Decimal("36.2") and k["food"].target == Decimal("0.32")
    assert mln(k["food"].gap_money) == Decimal("18.7") and k["food"].status == "problem"
    assert (k["labor"].value * 100).quantize(Decimal("0.1")) == Decimal("17.6")
    assert (k["prime"].value * 100).quantize(Decimal("0.1")) == Decimal("53.8")
    assert (k["rent"].value * 100).quantize(Decimal("0.1")) == Decimal("5.6")


def test_break_even_and_stress(s):
    be = cfo.break_even(s, OCT)
    assert near(be.cm_ratio, Decimal("0.536"), 5) and near(be.fixed / M, Decimal("130.6"), 5)
    assert near(be.be_checks_per_day, Decimal(74), 5) and near(be.cash_be_checks_per_day, Decimal(80), 5)
    assert be.checks_per_day.quantize(Decimal(1)) == 135
    st = cfo.stress_test(s, (20, 30), OCT)
    res = dict(st.drops)
    assert near(res[20] / M, Decimal(50), 10) and near(res[30] / M, Decimal(26), 10)
    assert near(st.max_drop_pct, Decimal(41), 10)


def test_debt_schedule(s):
    d = cfo.debt_schedule(s)
    assert d is not None and d.months_left == 26 and mln(d.balance) == Decimal("260.0")
    assert d.rows[0][1] == 10_000_000 and mln(d.rows[0][2]) == Decimal("5.2")

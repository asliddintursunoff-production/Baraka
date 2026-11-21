"""Spec §5.3 golden tests: exactly the DESIGN.md demo numbers, clean input, no rules."""

from datetime import date
from decimal import Decimal

import pytest

from apps.ai.uz_format import format_mln
from apps.engine import (
    Change,
    evaluate_purchase,
    explain_day,
    forecast,
    installment_schedule,
    simulate,
    spend_limit_until,
)

from .golden import TODAY, golden_input, mln

DEC10, JAN10, JAN12 = date(2026, 12, 10), date(2027, 1, 10), date(2027, 1, 12)


@pytest.fixture(scope="module")
def inp():
    return golden_input()


@pytest.fixture(scope="module", params=[60, 90])
def base(request, inp):
    return forecast(inp, request.param)


def test_baseline(base):
    assert base.min_balance == mln("18.815")
    assert format_mln(base.min_balance) == "18,8 mln"
    assert base.min_date == DEC10
    assert base.verdict == "yes"
    assert base.first_shortage_date is None
    assert base.insufficient_data is False


def test_buy_25_today(base, inp):
    s = simulate(base, inp, Change(kind="extra_expense", value=mln("25"), start_date=TODAY))
    assert s.min_balance == mln("-6.185")
    assert format_mln(s.min_balance) == "−6,2 mln"
    assert s.min_date == DEC10 and s.first_shortage_date == DEC10
    assert s.verdict == "no"


def test_buy_on_jan_12(base, inp):
    s = simulate(base, inp, Change(kind="extra_expense", value=mln("25"), start_date=JAN12))
    assert s.min_balance == mln("12.255")
    assert format_mln(s.min_balance) == "12,3 mln"
    assert s.min_date == JAN12
    assert s.verdict == "yes"


def test_installments_9_8_8(base, inp):
    schedule = installment_schedule(TODAY, mln("25"))
    assert schedule == (
        (date(2026, 11, 21), mln("9")),
        (date(2026, 12, 21), mln("8")),
        (date(2027, 1, 21), mln("8")),
    )
    s = simulate(base, inp, Change(kind="extra_expense", schedule=schedule))
    assert s.min_balance == mln("9.815")
    assert format_mln(s.min_balance) == "9,8 mln"
    assert s.verdict == "risky"


def test_revenue_minus_20(base, inp):
    s = simulate(base, inp, Change(kind="revenue_pct", value=Decimal(-20)))
    assert s.min_balance == mln("-7.504")
    assert format_mln(s.min_balance) == "−7,5 mln"
    assert s.min_date == JAN10
    assert s.verdict == "no"


def test_two_more_staff(base, inp):
    s = simulate(base, inp, Change(kind="new_staff", value=Decimal(2)))
    assert s.min_balance == mln("12.815")
    assert format_mln(s.min_balance) == "12,8 mln"
    assert s.min_date == DEC10
    assert s.verdict == "yes"


def test_spend_limit_until_dec_10(base):
    assert spend_limit_until(base, DEC10) == Decimal("8000000.00")


def test_evaluate_purchase_25(inp):
    d = evaluate_purchase(inp, mln("25"))
    assert d.verdict == "no"
    assert d.key_date == DEC10
    assert d.requested.balance_on_key_date == mln("-6.185")
    assert d.recommended is not None
    assert d.recommended.kind == "earliest_safe_date"
    assert d.recommended.schedule == ((JAN12, mln("25")),)
    assert d.recommended.verdict == "yes"
    assert d.recommended.balance_on_key_date == mln("18.815")  # "+18,8 mln" on 10-Dec
    split = next(a for a in d.alternatives if a.kind == "installments")
    assert split.verdict == "risky" and split.min_balance == mln("9.815")


def test_evaluate_purchase_yes_when_affordable(inp):
    d = evaluate_purchase(inp, mln("5"))
    assert d.verdict == "yes"
    assert d.recommended == d.requested
    assert d.alternatives == ()


@pytest.mark.parametrize(
    ("day", "close"),
    [
        (date(2026, 11, 25), "40.445"),
        (date(2026, 12, 1), "48.875"),
        (date(2026, 12, 9), "78.905"),
        (date(2026, 12, 15), "30.835"),
        (date(2026, 12, 25), "46.455"),
        (date(2027, 1, 10), "30.820"),
    ],
)
def test_mockup_cross_checks(base, day, close):
    # Forecast.html "Muhim kunlar" and Calendar.html balances
    assert base.close_on(day) == mln(close)


def test_explain_dec_10(base):
    b = explain_day(base, DEC10)
    assert b.opening == mln("78.905")  # "Kun boshida kassada 78,9 mln"
    assert b.revenue == mln("6.2")
    assert b.net_trading == mln("3.41")  # "Savdodan kiradi +3,4 mln"
    assert sorted(p.amount for p in b.payments) == [mln("18.5"), mln("45")]
    assert b.closing == mln("18.815")
    assert b.status == "ok" and b.is_lowest_day


def test_thirty_day_obligations_total(base):
    # Main.html KPI "30 kunda to'lashingiz shart · 108,5 mln · 5 ta to'lov"
    until = date(2026, 12, 21)
    due = [p for p in base.obligations if TODAY < p.date <= until]
    assert len(due) == 5
    assert sum(p.amount for p in due) == mln("108.5")

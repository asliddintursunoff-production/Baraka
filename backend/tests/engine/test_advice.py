"""Deferral advice (risky), data-based salary for new staff, spend limit from a date."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.engine import (
    Change,
    DailyActual,
    EngineInput,
    ObligationIn,
    ParamsIn,
    StaffCountUnknown,
    forecast,
    simulate,
    spend_limit_until,
)

from .golden import TODAY, golden_input, mln

AGRO = "Agro Go'sht"


def _tight(opening="5"):
    return EngineInput(
        today=TODAY,
        opening_balance=mln(opening),
        history=[DailyActual(TODAY - timedelta(days=i), mln("1")) for i in range(56)],
        obligations=[
            ObligationIn(
                title="Ta'minotchi",
                amount=mln("20"),
                due_date=date(2026, 11, 23),
                priority="deferrable",
                counterparty=AGRO,
                category="supplier",
            ),
            ObligationIn(
                title="Ijara",
                amount=mln("2"),
                due_date=date(2026, 12, 30),
                priority="critical",
                category="rent",
            ),
        ],
        params=ParamsIn(variable_cost_ratio=Decimal("0.5")),
        safe_min=mln("1"),
    )


def test_risky_shortage_on_deferrable_day_suggests_exact_delay():
    f = forecast(_tight(), 60)
    assert f.verdict == "risky" and f.first_shortage_date == date(2026, 11, 23)
    (d,) = f.deferrals
    # 5 + 0.5/day; after k extra days: 5 + (2 + k) * 0.5 - 20 >= 0  ->  k = 28
    assert d.obligation.counterparty == AGRO
    assert d.days == 28 and d.new_date == date(2026, 12, 21) and d.resolves


def test_no_deferral_when_verdict_is_yes_or_no():
    assert forecast(golden_input(), 60).deferrals == ()
    base = forecast(golden_input(), 60)
    s = simulate(base, golden_input(), Change(kind="extra_expense", value=mln("25")))
    assert s.verdict == "no" and s.deferrals == ()


def test_scenario_can_produce_deferral_advice():
    inp = _tight(opening="20")  # fine on its own
    base = forecast(inp, 60)
    assert base.verdict == "yes" or base.first_shortage_date is None
    s = simulate(base, inp, Change(kind="extra_expense", value=mln("4")))
    assert s.verdict == "risky" and s.deferrals and s.deferrals[0].resolves


def test_new_staff_salary_comes_from_last_payroll():
    inp = golden_input(last_payroll_amount=mln("60"))  # 60 / 15 = 4 mln per person
    s = simulate(forecast(inp, 60), inp, Change(kind="new_staff", value=Decimal(2)))
    assert s.min_balance == mln("18.815") - mln("8")


def test_new_staff_without_staff_count_asks():
    inp = golden_input(staff_count=None)
    with pytest.raises(StaffCountUnknown):
        simulate(forecast(inp, 60), inp, Change(kind="new_staff", value=Decimal(2)))


def test_new_staff_falls_back_to_planned_payroll_amount():
    inp = golden_input(last_payroll_amount=None)
    s = simulate(forecast(inp, 60), inp, Change(kind="new_staff", value=Decimal(2)))
    assert s.min_balance == mln("12.815")


def test_spend_limit_counts_from_purchase_date():
    base = forecast(golden_input(), 60)
    assert spend_limit_until(base, date(2026, 12, 10)) == mln("8")
    # buying on 11-Dec: that day itself (23,0) is the lowest from then on -> 12 mln
    assert spend_limit_until(base, date(2026, 12, 20), purchase_date=date(2026, 12, 11)) == mln(
        "12"
    )
    # buying on 16-Dec: the lowest later day is 10-Jan (30,8) -> 20 mln
    assert spend_limit_until(base, date(2026, 12, 20), purchase_date=date(2026, 12, 16)) == mln(
        "20"
    )
    with pytest.raises(ValueError):
        spend_limit_until(base, date(2026, 12, 10), purchase_date=date(2026, 12, 11))

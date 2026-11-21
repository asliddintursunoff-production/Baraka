"""One test group per rule type (spec §5.3), on the golden input."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.engine import (
    DailyActual,
    EngineError,
    EngineInput,
    ObligationIn,
    ParamsIn,
    RuleIn,
    TxnIn,
    aggregate_daily,
    forecast,
)

from .golden import TODAY, golden_input, mln

AGRO = "Agro Go'sht"


def base(rules=(), **kw):
    return forecast(golden_input(rules=list(rules), **kw), 60)


# --- payment_shift --------------------------------------------------------------------
def test_payment_shift_moves_supplier_by_15_days():
    rule = RuleIn(type="payment_shift", target={"counterparty": AGRO}, effect={"days": 15}, id="r1")
    plain, shifted = base(), base([rule])
    moved = [p for p in shifted.obligations if p.counterparty == AGRO]
    assert [p.date for p in moved] == [date(2026, 12, 10), date(2027, 1, 9)]
    assert all(p.due_date.day == 25 for p in moved)
    # 25-Nov is 22 mln better off; 10-Dec ends the same (the chat demo's point)
    assert shifted.close_on(date(2026, 11, 25)) == plain.close_on(date(2026, 11, 25)) + mln("22")
    assert shifted.min_balance == plain.min_balance == mln("18.815")
    assert shifted.min_date == date(2026, 12, 10)


def test_payment_shift_matches_names_loosely():
    rule = RuleIn(
        type="payment_shift", target={"counterparty": "  agro go’sht "}, effect={"days": 15}
    )
    assert base([rule]).close_on(date(2026, 11, 25)) == base().close_on(date(2026, 11, 25)) + mln(
        "22"
    )


def test_payment_shift_respects_explicit_expected_date():
    inp = golden_input()
    first = inp.obligations[0]
    fixed = ObligationIn(**{**first.__dict__, "expected_date": date(2026, 11, 27)})
    rule = RuleIn(type="payment_shift", target={"counterparty": AGRO}, effect={"days": 15})
    f = forecast(golden_input(rules=[rule], obligations=[fixed, *inp.obligations[1:]]), 60)
    assert next(p for p in f.obligations if p.due_date == first.due_date).date == date(2026, 11, 27)


# --- recurring ------------------------------------------------------------------------
SVET = RuleIn(
    type="recurring",
    target={"title": "Svet", "category": "utility"},
    effect={"amount": "2100000", "day_of_month": 3, "priority": "critical"},
    id="svet",
)


def test_recurring_adds_monthly_payment():
    f = base([SVET])
    svet = [p for p in f.obligations if p.title == "Svet"]
    assert [p.date for p in svet] == [date(2026, 12, 3), date(2027, 1, 3)]
    assert all(p.source == "rule" and p.rule_id == "svet" for p in svet)
    assert f.min_balance == mln("18.815") - mln("2.1")


def test_recurring_does_not_duplicate_existing_payment():
    inp = golden_input()
    existing = ObligationIn(
        title="svet", amount=mln("2.3"), due_date=date(2026, 12, 4), priority="critical"
    )
    f = forecast(golden_input(rules=[SVET], obligations=[*inp.obligations, existing]), 60)
    dec = [p for p in f.obligations if p.title.lower() == "svet" and p.date.month == 12]
    assert len(dec) == 1 and dec[0].amount == mln("2.3")


def test_recurring_validity_window():
    rule = RuleIn(
        type="recurring",
        target={"title": "Svet"},
        effect={"amount": "2100000", "day_of_month": 3, "from": "2027-01-01"},
    )
    assert [p.date for p in base([rule]).obligations if p.title == "Svet"] == [date(2027, 1, 3)]


# --- weekday_factor -------------------------------------------------------------------
def test_weekday_factor_in_absolute_period():
    rule = RuleIn(
        type="weekday_factor",
        target={"weekdays": [4]},  # Friday
        effect={"multiplier": "1.5", "period": {"from": "2026-11-27", "to": "2026-11-27"}},
        id="fri",
    )
    plain, boosted = base(), base([rule])
    # Friday 27-Nov: +50% of 7.6 mln sales, 55% of it stays in cash
    extra = mln("7.6") * Decimal("0.5") * Decimal("0.55")
    assert boosted.close_on(date(2026, 11, 26)) == plain.close_on(date(2026, 11, 26))
    assert boosted.close_on(date(2026, 11, 27)) == plain.close_on(date(2026, 11, 27)) + extra
    assert boosted.close_on(date(2026, 12, 4)) == plain.close_on(date(2026, 12, 4)) + extra


def test_weekday_factor_yearly_navruz_is_neutral_in_winter():
    navruz = RuleIn(
        type="weekday_factor",
        target={"weekdays": [4, 5]},
        effect={"multiplier": "1.2", "period": {"from": "03-14", "to": "03-21"}},
        id="navruz",
    )
    f = base([navruz])
    assert f.min_balance == mln("18.815")
    assert (f.close == base().close).all()
    march = date(2027, 3, 1)
    shift = march - TODAY
    hist = [DailyActual(h.date + shift, h.inflow, h.outflow) for h in golden_input().history]
    spring = forecast(golden_input(rules=[navruz], today=march, hist=hist, obligations=[]), 30)
    plain_spring = forecast(golden_input(today=march, hist=hist, obligations=[]), 30)
    # Fri 19-Mar and Sat 14/20-Mar are inside 14..21 March: 3 boosted days
    assert spring.close_on(date(2027, 3, 13)) == plain_spring.close_on(date(2027, 3, 13))
    assert spring.close_on(date(2027, 3, 31)) > plain_spring.close_on(date(2027, 3, 31))


# --- priority ---------------------------------------------------------------------------
def _tight_input(rules):
    """One supplier payment that drives cash below zero, nothing critical."""
    return EngineInput(
        today=TODAY,
        opening_balance=mln("5"),
        history=[DailyActual(TODAY - timedelta(days=i), mln("1")) for i in range(56)],
        obligations=[
            ObligationIn(
                title="Ta'minotchi",
                amount=mln("20"),
                due_date=date(2026, 11, 23),
                priority="deferrable",
                counterparty=AGRO,
            )
        ],
        rules=rules,
        params=ParamsIn(variable_cost_ratio=Decimal("0.5")),
        safe_min=mln("1"),
    )


def test_priority_rule_turns_shortage_into_no():
    assert forecast(_tight_input([]), 30).verdict == "risky"  # only a deferrable payment fails
    rule = RuleIn(type="priority", target={"counterparty": AGRO}, effect={"level": "critical"})
    f = forecast(_tight_input([rule]), 30)
    assert f.verdict == "no"
    assert f.critical_mask[2]


# --- ignore -----------------------------------------------------------------------------
def test_ignore_rule_drops_obligations():
    rule = RuleIn(type="ignore", target={"counterparty": AGRO}, id="ign")
    f = base([rule])
    assert not [p for p in f.obligations if p.counterparty == AGRO]
    assert f.min_balance == mln("18.815") + mln("22")


def test_ignore_rule_in_history_aggregation():
    rules = [RuleIn(type="ignore", target={"category": "Ichki o'tkazma"})]
    txns = [
        TxnIn(TODAY, mln("5"), "in", category="savdo"),
        TxnIn(TODAY, mln("50"), "in", category="ichki o’tkazma"),
        TxnIn(TODAY, mln("2"), "out", category="go'sht"),
    ]
    days = aggregate_daily(txns, rules, start=TODAY - timedelta(days=1), end=TODAY)
    assert [(d.inflow, d.outflow) for d in days] == [(0, 0), (mln("5"), mln("2"))]


# --- general ----------------------------------------------------------------------------
def test_disabled_rules_are_skipped():
    rule = RuleIn(type="ignore", target={"counterparty": AGRO}, enabled=False)
    assert base([rule]).min_balance == mln("18.815")


@pytest.mark.parametrize(
    "rule",
    [
        RuleIn(type="nonsense", target={}),  # type: ignore[arg-type]
        RuleIn(type="payment_shift", target={"counterparty": AGRO}, effect={"days": "15"}),
        RuleIn(type="recurring", target={"title": "x"}, effect={"amount": 2.5, "day_of_month": 3}),
        RuleIn(type="weekday_factor", target={"weekday": 9}, effect={"multiplier": "1.1"}),
        RuleIn(type="priority", target={"title": "x"}, effect={"level": "urgent"}),
        RuleIn(type="ignore", target={}),
    ],
)
def test_invalid_rules_raise(rule):
    with pytest.raises(EngineError):
        base([rule])

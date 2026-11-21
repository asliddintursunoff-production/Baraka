"""Revenue model, uncertainty band, insufficient data, segment blending, serialization."""

from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

import numpy as np
import pytest

from apps.engine import (
    Change,
    DailyActual,
    EngineError,
    ObligationIn,
    ParamsIn,
    RuleIn,
    SegmentPriorIn,
    evaluate_purchase,
    explain_day,
    forecast,
    input_from_dict,
    input_to_dict,
    inputs_hash,
    simulate,
)

from .golden import TODAY, WEEKDAY_REVENUE, golden_input, history, mln

NOISE = {
    wd: [mln(x) for x in ("0.6", "-0.4", "0.3", "-0.5", "0.2", "-0.2", "0.4", "-0.4")]
    for wd in range(7)
}


def test_constant_history_has_zero_band_and_high_confidence():
    f = forecast(golden_input(), 60)
    assert int(f.band.max()) == 0
    assert f.confidence == "high"
    assert f.weekday_revenue == tuple(v.quantize(Decimal("0.01")) for v in WEEKDAY_REVENUE)


def test_noisy_history_keeps_means_and_widens_band():
    noisy = forecast(golden_input(hist=history(noise=NOISE)), 60)
    assert noisy.min_balance == mln("18.815")  # zero-sum noise: same weekday averages
    band = noisy.band
    assert band[0] == 0 and band[-1] > band[1] > 0
    assert np.all(np.diff(band) >= 0)
    rows = noisy.daily()
    assert all(r.p10 <= r.close <= r.p90 for r in rows)
    assert rows[1].p90 - rows[1].close == rows[1].close - rows[1].p10
    assert noisy.confidence in {"high", "medium", "low"}


def test_band_grows_like_sigma_sqrt_t():
    hist = [
        DailyActual(TODAY - timedelta(days=i), mln("10") + (mln("1") if i % 2 else -mln("1")))
        for i in range(56)
    ]
    f = forecast(golden_input(hist=hist, obligations=[]), 28)
    # same weekday spread every day -> band(4t) = 2 * band(t)
    assert abs(int(f.band[28]) - 2 * int(f.band[7])) <= 2


def test_insufficient_data_without_segment():
    hist = history(weeks=8)[-10:]  # 10 days
    f = forecast(golden_input(hist=hist), 60)
    assert f.insufficient_data and f.verdict is None and f.confidence is None
    d = evaluate_purchase(golden_input(hist=hist), mln("25"))
    assert d.insufficient_data and d.verdict is None and d.recommended is None
    s = simulate(f, golden_input(hist=hist), Change(kind="revenue_pct", value=Decimal(-20)))
    assert s.verdict is None


def test_no_history_at_all_is_insufficient_even_with_segment():
    prior = SegmentPriorIn(weekday_shape=(1,) * 7, n_businesses=6)
    f = forecast(golden_input(hist=[], segment_prior=prior), 30)
    assert f.insufficient_data


def test_segment_blend_weight_and_shape():
    shape = (0.8, 0.8, 0.9, 0.9, 1.1, 1.3, 1.2)
    prior = SegmentPriorIn(weekday_shape=shape, n_businesses=6)
    hist = [DailyActual(TODAY - timedelta(days=i), mln("7")) for i in range(28)]  # flat 4 weeks
    f = forecast(golden_input(hist=hist, segment_prior=prior), 30)
    assert not f.insufficient_data
    assert f.segment_weight == 0.5  # 1 - min(1, 4/8)
    mean_shape = sum(shape) / 7
    for wd in range(7):
        expected = 0.5 * 7_000_000 + 0.5 * 7_000_000 * shape[wd] / mean_shape
        assert abs(float(f.weekday_revenue[wd]) - expected) < 0.01
    ten_days = forecast(golden_input(hist=hist[:10], segment_prior=prior), 30)
    assert ten_days.segment_weight == round(1 - (10 / 7) / 8, 4) and not ten_days.insufficient_data
    full = forecast(golden_input(segment_prior=prior), 30)
    assert full.segment_weight == 0.0


def test_unpaid_overdue_payment_hits_today():
    overdue = ObligationIn(
        title="Eski qarz", amount=mln("3"), due_date=TODAY - timedelta(days=2), priority="critical"
    )
    inp = golden_input(obligations=[overdue])
    f = forecast(inp, 30)
    assert f.close_on(TODAY) == mln("45.2")
    b = explain_day(f, TODAY)
    assert b.opening == mln("48.2") and b.payments[0].title == "Eski qarz"


def test_money_must_be_decimal():
    with pytest.raises(EngineError):
        forecast(golden_input(opening_balance=48_200_000), 30)
    with pytest.raises(EngineError):
        forecast(golden_input(params=ParamsIn(variable_cost_ratio=0.45)), 30)
    with pytest.raises(EngineError):
        simulate(
            forecast(golden_input(), 30), golden_input(), Change(kind="extra_expense", value=5.0)
        )


def test_change_validation():
    inp = golden_input()
    f = forecast(inp, 60)
    with pytest.raises(EngineError):
        simulate(f, inp, Change(kind="new_staff", value=Decimal("1.5")))
    with pytest.raises(EngineError):
        simulate(f, golden_input(staff_count=None), Change(kind="new_staff", value=Decimal(2)))
    with pytest.raises(EngineError):
        simulate(f, inp, Change(kind="payment_delay", value=Decimal(5), counterparty="Nobody"))
    with pytest.raises(EngineError):
        simulate(
            f,
            inp,
            Change(kind="extra_expense", value=mln("1"), start_date=TODAY - timedelta(days=1)),
        )


def test_payment_delay_moves_critical_day():
    inp = golden_input()
    f = forecast(inp, 60)
    s = simulate(f, inp, Change(kind="payment_delay", value=Decimal(5), counterparty="NBU"))
    assert s.close_on(date(2026, 12, 10)) == mln("18.815") + mln("18.5")
    assert s.critical_mask[(date(2026, 12, 15) - TODAY).days]
    assert s.verdict == "yes"


def test_results_are_read_only():
    f = forecast(golden_input(), 30)
    with pytest.raises(ValueError):
        f.close[0] = 0


def test_serialization_round_trip_and_stable_hash():
    rules = [
        RuleIn(
            type="payment_shift",
            target={"counterparty": "Agro Go'sht"},
            effect={"days": 15},
            id="1",
        )
    ]
    inp = golden_input(rules=rules)
    again = input_from_dict(input_to_dict(inp))
    assert inputs_hash(again) == inputs_hash(inp)
    assert (forecast(again, 60).close == forecast(inp, 60).close).all()
    reordered = golden_input(
        rules=[
            RuleIn(
                type="payment_shift",
                effect={"days": 15},
                target={"counterparty": "Agro Go'sht"},
                id="1",
            )
        ]
    )
    assert inputs_hash(reordered) == inputs_hash(inp)
    changed = golden_input(rules=rules, opening_balance=mln("48.3"))
    assert inputs_hash(changed) != inputs_hash(inp)


def test_daily_rows_shape_for_snapshot():
    rows = forecast(golden_input(), 60).daily()
    assert len(rows) == 61 and rows[0].date == TODAY
    assert rows[0].open == rows[0].close == mln("48.2")
    for prev, row in pairwise(rows):
        assert row.open == prev.close
        assert row.close == row.open + row.inflow - row.outflow

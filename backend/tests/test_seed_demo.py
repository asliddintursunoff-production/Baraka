"""Seed data relative to "today": checked on 62 consecutive days per window.

Each day: lowest balance in the next 60 days within 18-20 mln, "buy 25 mln" -> no, and a
safe purchase date is recommended. Windows cover month ends (30/31), February and the day
before payroll (9th).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.engine import evaluate_purchase, forecast
from apps.finance.demo import build_navroz, build_peers, engine_input

WINDOWS = (date(2026, 11, 21), date(2027, 1, 1))
DAYS = [start + timedelta(days=k) for start in WINDOWS for k in range(62)]
M = Decimal(1_000_000)


def test_windows_cover_the_hard_calendar_cases():
    assert {date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31), date(2027, 2, 28)} <= set(
        DAYS
    )
    assert any(d.day == 9 for d in DAYS) and any(d.month == 2 for d in DAYS)


@pytest.mark.parametrize("today", DAYS, ids=lambda d: d.isoformat())
def test_demo_cash_story_holds_every_day(today):
    biz = build_navroz(today)
    inp = engine_input(biz, biz.closing_cash_today)
    f = forecast(inp, 60)
    assert 18 * M <= f.min_balance <= 20 * M
    d = evaluate_purchase(inp, 25 * M)
    assert d.verdict == "no"
    assert d.recommended is not None and d.recommended.kind == "earliest_safe_date"
    assert d.recommended.verdict == "yes"


def test_design_day_reproduces_mockup_story():
    biz = build_navroz(date(2026, 11, 21))
    f = forecast(engine_input(biz, biz.closing_cash_today), 60)
    assert f.min_date == date(2026, 12, 10)
    assert f.verdict == "yes"
    assert biz.staff_count == 15 and sum(e.salary for e in biz.employees) == 45 * M


def test_last_eight_weeks_have_exact_weekday_averages():
    today = date(2026, 11, 21)
    biz = build_navroz(today)
    inp = engine_input(biz, biz.closing_cash_today)
    expected = [Decimal(x) * M for x in ("5.8", "5.9", "6.0", "6.2", "7.6", "8.9", "8.2")]
    assert list(forecast(inp, 30).weekday_revenue) == expected


def test_svet_pattern_exists_for_ai_to_notice():
    biz = build_navroz(date(2026, 11, 21))
    svet = [t for t in biz.txns if t.note == "Svet"]
    assert len(svet) >= 3
    assert all(abs(t.date.day - 3) <= 1 for t in svet)


def test_peers_share_the_segment_band():
    from apps.finance.demo import revenue_band

    today = date(2026, 11, 21)
    bands = set()
    for biz in [build_navroz(today), *build_peers(today)]:
        monthly = sum(biz.weekday_revenue) / 7 * 30
        bands.add(revenue_band(monthly))
    assert bands == {"100_300"}

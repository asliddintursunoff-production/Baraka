"""trend_watch (C9): a synthetic 3-week decline gives exactly one alert, deduped on re-run."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.engine.trend import trailing_streak, trend_watch
from apps.finance.models import CashAccount, Transaction
from apps.insights.alerts import evaluate_alerts
from apps.insights.models import Alert
from apps.insights.trends import weekly_series
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business

W = [date(2026, 9, 7) + timedelta(weeks=i) for i in range(6)]


def pts(*xs):
    return [(w, Decimal(x)) for w, x in zip(W, xs, strict=False)]


def test_streak_needs_three_wrong_way_weeks():
    assert trailing_streak("sales", pts(100, 100, 90, 80), "down") is None  # 2 declines
    t = trailing_streak("sales", pts(100, 100, 90, 80, 70), "down")
    assert t and t.weeks == 3 and t.start == W[1] and t.change_pct == Decimal("-0.3")
    assert trailing_streak("sales", pts(100, 99, 98, 97.5), "down") is None  # < 5 % total
    assert trailing_streak("expense_ratio", pts("0.5", "0.55", "0.6", "0.7"), "up").weeks == 3
    assert trend_watch({"sales": pts(100, 110, 120, 130)}, {"sales": "down"}) == []


@pytest.mark.django_db
def test_synthetic_three_week_decline_gives_one_alert(monkeypatch):
    from apps.insights import trends

    b = Business.objects.create(name="Trend", is_demo=True)
    monkeypatch.setattr("apps.insights.alerts.find_alerts", lambda r: [])
    with tenant_context(b):
        CashAccount.objects.create(
            business=b, opening_balance=Decimal(500_000_000), as_of_date=W[0] - timedelta(days=1)
        )
        # 5 weeks of sales; flat expenses; sales fall in each of the last 3 weeks
        weekly = [70, 70, 63, 56, 49]
        for w, s in zip(W, weekly, strict=False):
            for d in range(7):
                day = w + timedelta(days=d)
                Transaction.objects.create(
                    business=b,
                    txn_date=day,
                    amount=Decimal(s * 1_000_000 // 7),
                    direction="in",
                    category="sales",
                    is_actual=True,
                )
                Transaction.objects.create(
                    business=b,
                    txn_date=day,
                    amount=Decimal(3_000_000),
                    direction="out",
                    category="supplies",
                    is_actual=True,
                )
        ser = weekly_series(W[4] + timedelta(days=6))
        assert [x for _, x in ser["sales"]][-3:] == sorted(
            [x for _, x in ser["sales"]][-3:], reverse=True
        )
        found = trends.find_trends(W[4] + timedelta(days=6))
    assert {t.metric for t in found} == {"sales", "expense_ratio", "net"}  # one per metric
    monkeypatch.setattr(
        "apps.insights.trends.find_trends", lambda last: [t for t in found if t.metric == "sales"]
    )
    assert evaluate_alerts(b) == 1
    assert evaluate_alerts(b) == 0  # deduped
    with tenant_context(b):
        a = Alert.objects.get(kind="trend_sales")
    assert "3 hafta ketma-ket tushmoqda" in a.text_uz and a.status == "new"

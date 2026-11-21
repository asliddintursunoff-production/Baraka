"""Weekly metrics from actual transactions -> apps.engine.trend.trend_watch (Part C9).

Metrics: weekly sales (bad: down), operating expenses as a share of sales (bad: up), weekly
operating net (bad: down). Only complete Mon-Sun weeks up to the last actual day.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum

from apps.ai import uz_format as uz
from apps.engine.trend import Trend, trend_watch
from apps.finance.models import Transaction

WEEKS = 12
NOT_SALES = ("financing", "capex", "dividend", "avans")
NOT_OPEX = ("financing", "capex", "dividend", "avans", "loan")
BAD = {"sales": "down", "expense_ratio": "up", "net": "down"}
LABEL = {
    "sales": "Haftalik savdo",
    "expense_ratio": "Xarajat / savdo ulushi",
    "net": "Haftalik sof pul",
}


def weekly_series(last: date, weeks: int = WEEKS) -> dict[str, list[tuple[date, Decimal]]]:
    """Inside the tenant context. Weeks are Monday-starting and end on or before `last`."""
    end_week = last - timedelta(days=(last.weekday() + 1) % 7)  # last complete Sunday
    start = end_week - timedelta(days=7 * weeks - 1)
    rows = (
        Transaction.objects.filter(is_actual=True, txn_date__gte=start, txn_date__lte=end_week)
        .values("txn_date")
        .annotate(
            s=Sum("amount", filter=Q(direction="in") & ~Q(category__in=NOT_SALES)),
            o=Sum("amount", filter=Q(direction="out") & ~Q(category__in=NOT_OPEX)),
        )
    )
    by_week: dict[date, list[Decimal]] = {}
    for r in rows:
        wk = r["txn_date"] - timedelta(days=r["txn_date"].weekday())
        acc = by_week.setdefault(wk, [Decimal(0), Decimal(0)])
        acc[0] += r["s"] or 0
        acc[1] += r["o"] or 0
    weeks_sorted = sorted(w for w, v in by_week.items() if v[0] > 0)
    return {
        "sales": [(w, by_week[w][0]) for w in weeks_sorted],
        "expense_ratio": [
            (w, (by_week[w][1] / by_week[w][0]).quantize(Decimal("0.0001"))) for w in weeks_sorted
        ],
        "net": [(w, by_week[w][0] - by_week[w][1]) for w in weeks_sorted],
    }


def value_text(metric: str, x: Decimal) -> str:
    return (
        f"{(x * 100).quantize(Decimal('0.1'))}%".replace(".", ",")
        if metric == "expense_ratio"
        else uz.format_mln(x)
    )


def trend_text(t: Trend) -> str:
    change = f"{(t.change_pct * 100).quantize(Decimal(1))}%"
    move = "o'smoqda" if t.bad == "up" else "tushmoqda"
    tip = {
        "sales": "Sababini tekshiring: cheklar soni kamaydimi yoki o'rtacha chek?",
        "expense_ratio": "Qaysi xarajat o'sganini ko'ring — ko'pincha mahsulot narxi yoki agregator komissiyasi.",
        "net": "Savdo va xarajatlarni haftama-hafta solishtiring.",
    }[t.metric]
    return (
        f"{LABEL[t.metric]} {t.weeks} hafta ketma-ket {move}: {uz.format_date(t.start)} {t.start.year} haftasida "
        f"{value_text(t.metric, t.first)}, {uz.format_date(t.end)} {t.end.year} haftasida {value_text(t.metric, t.last)} "
        f"({change}). {tip}"
    )


def find_trends(last: date) -> list[Trend]:
    return trend_watch(weekly_series(last), BAD)


def as_dict(t: Trend) -> dict[str, Any]:
    return {
        "metric": t.metric,
        "label": LABEL[t.metric],
        "weeks": t.weeks,
        "start": t.start.isoformat(),
        "end": t.end.isoformat(),
        "first": value_text(t.metric, t.first),
        "last": value_text(t.metric, t.last),
        "change_pct": str((t.change_pct * 100).quantize(Decimal("0.1"))),
        "text": trend_text(t),
    }

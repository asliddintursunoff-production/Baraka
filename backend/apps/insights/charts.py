"""Two-panel chart data (Part B): actual history | forecast, one snapshot, dates with year.

history: daily actual closing cash up to the last actual day (12 months), weekly in/out,
         markers for big one-offs (owner money, loans, capex), a deterministic caption.
forecast extras: the gap (last actual day -> today, "Ma'lumot kiritilmagan"), today, the
         hardest-day marker with that day's payments, and a caption for the 60-day story.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum

from apps.ai import uz_format as uz
from apps.engine.types import ForecastResult
from apps.finance.models import CashAccount, Transaction

from . import advice

HISTORY_DAYS = 366
ONE_OFF = ("financing", "capex", "dividend")


def date_long(d: date) -> str:
    """ "10-yanvar 2027, shanba" (tooltips, callouts)."""
    return f"{uz.format_date(d)} {d.year}, {uz.WEEKDAYS[d.weekday()]}"


def date_y(d: date) -> str:
    """ "10-yanvar 2027" (captions, cards, steps)."""
    return f"{uz.format_date(d)} {d.year}"


def history_block(base: ForecastResult) -> dict[str, Any] | None:
    """Inside the tenant context. None when there is no opening cash."""
    cash = CashAccount.objects.order_by("-as_of_date").first()
    if cash is None:
        return None
    last = base.today
    start = max(cash.as_of_date + timedelta(days=1), last - timedelta(days=HISTORY_DAYS))
    before = Transaction.objects.filter(
        is_actual=True, txn_date__gt=cash.as_of_date, txn_date__lt=start
    ).aggregate(
        i=Sum("amount", filter=Q(direction="in")), o=Sum("amount", filter=Q(direction="out"))
    )
    running = (
        Decimal(cash.opening_balance) + (before["i"] or Decimal(0)) - (before["o"] or Decimal(0))
    )
    days: dict[date, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for r in (
        Transaction.objects.filter(is_actual=True, txn_date__gte=start, txn_date__lte=last)
        .values("txn_date", "direction")
        .annotate(s=Sum("amount"))
    ):
        days[r["txn_date"]][0 if r["direction"] == "in" else 1] += r["s"]
    points = []
    weekly: dict[date, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    d = start
    while d <= last:
        i, o = days.get(d, [Decimal(0), Decimal(0)])
        running += i - o
        points.append({"date": d.isoformat(), "close": str(running.quantize(Decimal("0.01")))})
        wk = d - timedelta(days=d.weekday())
        weekly[wk][0] += i
        weekly[wk][1] += o
        d += timedelta(days=1)
    threshold = max(Decimal(50_000_000), abs(running) * Decimal("0.05"))
    markers = [
        {
            "date": t["txn_date"].isoformat(),
            "label": f"{(t['note'] or '').split(' · ')[0] or 'Bir martalik'} {uz.format_mln(t['amount'])}",
            "amount": str(t["amount"] if t["direction"] == "in" else -t["amount"]),
        }
        for t in Transaction.objects.filter(
            is_actual=True,
            txn_date__gte=start,
            txn_date__lte=last,
            category__in=ONE_OFF,
            amount__gte=threshold,
        )
        .values("txn_date", "note", "amount", "direction")
        .order_by("txn_date")
    ]
    close_now = running
    ref = last - timedelta(days=91)
    then = next((Decimal(p["close"]) for p in points if p["date"] >= ref.isoformat()), None)
    caption = f"{date_y(last)} holatida kassa {uz.format_mln(close_now)}"
    if then is not None:
        delta = close_now - then
        caption += f"; 3 oyda {uz.format_mln(abs(delta))} {'o' + chr(39) + 'sdi' if delta >= 0 else 'kamaydi'}."
    else:
        caption += "."
    return {
        "title": "O'tgan davr — haqiqiy",
        "points": points,
        "weekly": [
            {"week": w.isoformat(), "in": str(v[0]), "out": str(v[1])}
            for w, v in sorted(weekly.items())
        ],
        "markers": markers,
        "last_actual": last.isoformat(),
        "caption": caption,
    }


def forecast_extras(base: ForecastResult, real_today: date, days: int = 60) -> dict[str, Any]:
    d = base.min_date
    pays = advice.payments_on(base, d)
    safe = (
        "Xavfsiz chegaradan yuqori."
        if base.min_balance >= base.safe_min
        else ("Xavfsiz chegaradan past." if base.min_balance >= 0 else "Pul yetmaydi.")
    )
    gap = None
    if real_today > base.today + timedelta(days=1):
        gap = {
            "from": (base.today + timedelta(days=1)).isoformat(),
            "to": real_today.isoformat(),
            "label": "Ma'lumot kiritilmagan",
        }
    return {
        "title": f"Prognoz — keyingi {days} kun",
        "start": base.today.isoformat(),
        "today": real_today.isoformat(),
        "gap": gap,
        "hardest": {
            "date": d.isoformat(),
            "label": date_long(d),
            "balance": uz.format_mln(base.min_balance),
            "payments": [{"title": p.title, "amount": uz.format_mln(p.amount)} for p in pays],
        },
        "caption": f"Keyingi {days} kunda eng qiyin kun — {date_y(d)}: {uz.format_mln(base.min_balance)} qoladi. {safe}",
        "beyond": (
            f"{days} kundan keyin: {date_y(base.beyond[0])} kuni kassa {uz.format_mln(base.beyond[1])} gacha tushadi."
            if base.beyond
            else ""
        ),
    }

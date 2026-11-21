"""Proactive alerts (M6): three template rules over the cached forecast, no LLM.

1. `negative_critical`: the balance goes below zero on a day with a critical payment.
2. `below_safe_min`: the balance drops under the business's safe minimum (but not below 0).
3. `payroll_loan_week`: salary and loan payments fall in the same week.
4. `trend_*` (trend_watch): a weekly metric moved the wrong way 3+ weeks in a row; the key is
   the week the streak started, so a continuing streak updates one alert.

Each alert has a `dedupe_key` (business, kind, date): re-evaluation updates the text and
amount instead of creating a duplicate, and alerts whose condition is gone are dismissed.
The 08:00 brief (`daily_brief`) is also a template over the same forecast.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from apps.ai import uz_format as uz
from apps.engine.types import ForecastResult, PreparedObligation
from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business
from config import app_settings as cfg

from . import advice
from .forecasting import get_forecast
from .models import Alert

log = logging.getLogger(__name__)
TREND_KINDS = ("trend_sales", "trend_expense_ratio", "trend_net")
RULE_KINDS = ("negative_critical", "below_safe_min", "payroll_loan_week", *TREND_KINDS)


@dataclass(frozen=True)
class Found:
    kind: str
    severity: str
    date: date
    amount: Decimal | None
    text: str


def _critical_days(r: ForecastResult, end: date) -> dict[date, list[PreparedObligation]]:
    days: dict[date, list[PreparedObligation]] = {}
    for o in r.obligations:
        if o.priority == "critical" and r.today <= o.date <= end:
            days.setdefault(o.date, []).append(o)
    return days


def find_alerts(r: ForecastResult) -> list[Found]:
    if r.insufficient_data:
        return []
    end = r.today + timedelta(days=min(cfg.ALERT_HORIZON_DAYS, r.horizon_days - 1))
    out: list[Found] = []
    # 1. negative balance on a critical payment day
    for d, pays in sorted(_critical_days(r, end).items()):
        close = r.close_on(d)
        if close < 0:
            words = advice.join_uz([advice.payment_word(p) for p in pays])
            out.append(
                Found(
                    "negative_critical",
                    "danger",
                    d,
                    close,
                    f"{uz.format_date(d, 'da')} {words} kuni kassada {uz.format_mln(close)} bo'ladi — "
                    f"pul yetmaydi. Hozirdan katta xarajatlarni to'xtating yoki bitta to'lovni suring.",
                )
            )
    # 2. below the safe minimum (first day of each dip, not already negative-critical)
    neg_days = {f.date for f in out}
    d, prev_low = r.today, False
    while d <= end:
        close = r.close_on(d)
        low = Decimal(0) <= close < r.safe_min
        if low and not prev_low and d not in neg_days:
            out.append(
                Found(
                    "below_safe_min",
                    "warn",
                    d,
                    close,
                    f"{uz.format_date(d, 'da')} kassa {uz.format_mln(close)} gacha tushadi — "
                    f"xavfsiz chegara {uz.format_mln(r.safe_min)} dan past. "
                    f"{uz.format_date(d, 'gacha')} katta xarid qilmang.",
                )
            )
        prev_low = low or close < 0
        d += timedelta(days=1)
    # 3. salary and loan in the same week
    payroll = [o for o in r.obligations if o.category == "payroll" and r.today <= o.date <= end]
    loans = [o for o in r.obligations if o.category == "loan" and r.today <= o.date <= end]
    for p in payroll:
        same = [ln for ln in loans if abs((ln.date - p.date).days) < 7]
        if same:
            ln = same[0]
            total = p.amount + ln.amount
            first = min(p.date, ln.date)
            when = (
                uz.format_date(p.date)
                if p.date == ln.date
                else f"{uz.format_date(first)} – {uz.format_date(max(p.date, ln.date))}"
            )
            out.append(
                Found(
                    "payroll_loan_week",
                    "warn",
                    first,
                    total,
                    f"Bir haftada ish haqi ({uz.format_mln(p.amount)}) va kredit ({uz.format_mln(ln.amount)}) "
                    f"to'lovi: {when}. Jami {uz.format_mln(total)} — shu kungacha pul yig'ib qo'ying.",
                )
            )
    return out


def evaluate_alerts(business: Business) -> int:
    """Create/update alerts for the current forecast; returns the number of new alerts."""
    r = get_forecast(business).result
    found = find_alerts(r)
    created = 0
    with tenant_context(business):
        if not r.insufficient_data:
            from .trends import find_trends, trend_text

            found += [
                Found(
                    f"trend_{t.metric}",
                    "warn",
                    t.start,
                    None if t.metric == "expense_ratio" else t.last - t.first,
                    trend_text(t),
                )
                for t in find_trends(r.today)
            ]
        keys = set()
        for f in found:
            key = f"{business.pk}:{f.kind}:{f.date.isoformat()}"
            keys.add(key)
            _, new = Alert.objects.update_or_create(
                dedupe_key=key,
                defaults={
                    "business": business,
                    "kind": f.kind,
                    "severity": f.severity,
                    "date": f.date,
                    "amount": f.amount,
                    "text_uz": f.text,
                },
            )
            created += int(new)
        Alert.objects.filter(kind__in=RULE_KINDS).exclude(status=Alert.Status.DISMISSED).exclude(
            dedupe_key__in=keys
        ).update(status=Alert.Status.DISMISSED)
    if created:
        log.info("alerts: business %s, %s new", business.pk, created)
    return created


def brief_text(r: ForecastResult) -> str:
    """The 08:00 brief: a template over the forecast (never an LLM)."""
    if r.insufficient_data:
        return "Xayrli tong! Prognoz uchun ma'lumot hali yetarli emas — jadvalni to'ldirib boring."
    today = r.today
    pays = [o for o in r.obligations if o.date == today]
    b = advice.banner(r)
    parts = [f"Xayrli tong! Kassada {uz.format_mln(r.close_on(today))}."]
    if pays:
        parts.append(
            "Bugun: "
            + advice.join_uz(
                [f"{advice.payment_word(p)} ({uz.format_mln(p.amount)})" for p in pays]
            )
            + "."
        )
    parts.append(
        f"Eng qiyin kun: {uz.format_date(r.min_date)}, kassada {uz.format_mln(r.min_balance)}."
    )
    parts.append(f"{b['headline']} {b['instruction']}".strip())
    return " ".join(parts)


def daily_brief(business: Business) -> Alert:
    r = get_forecast(business).result
    with tenant_context(business):
        a: Alert
        a, _ = Alert.objects.update_or_create(
            dedupe_key=f"{business.pk}:brief:{r.today.isoformat()}",
            defaults={
                "business": business,
                "kind": "brief",
                "severity": "info",
                "date": r.today,
                "text_uz": brief_text(r),
            },
        )
    return a

"""A user's own, separate demo business ("Demo kafe bilan sinab ko'rish").

Seeded with the same generator as `seed_demo` (Navro'z data relative to today), tagged
`demo_user` so `seed_demo --reset` and segment statistics leave it alone, and marked
`is_demo` so the UI shows the "Demo" badge. The user's real business is never touched.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.tenancy.context import today_for
from apps.tenancy.models import Business, Membership

DEMO_TAG = "demo_user"
DEMO_NAME = "Demo kafe"


def demo_business_for(user: Any) -> Business:
    m = (
        Membership.objects.filter(user=user, business__is_demo=True)
        .select_related("business")
        .order_by("id")
        .first()
    )
    if m is not None:
        return m.business
    from apps.finance.demo import build_navroz
    from apps.finance.management.commands.seed_demo import Command
    from apps.insights.alerts import evaluate_alerts
    from apps.insights.forecasting import refresh_forecast

    probe = Business(timezone="Asia/Tashkent")
    biz = build_navroz(today_for(probe))
    with transaction.atomic():
        b = Command()._business(
            biz, {"owner": user, "accountant": user}, tag=DEMO_TAG, name=DEMO_NAME
        )
    refresh_forecast(b)
    evaluate_alerts(b)
    return b

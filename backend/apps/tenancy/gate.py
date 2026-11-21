"""The "no data, no answer" rule (design/DESIGN_ONBOARDING.md).

`data_status`: no_data (no confirmed + synced source) | short_history (< MIN_HISTORY_DAYS of
actual data) | ok. A seeded demo business is always ok. `onboarding_step` drives the
frontend guard. The backend is the authority: views with `requires_data` answer
409 {"code": "no_data"} while data_status is no_data.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Min
from rest_framework.exceptions import APIException

from config import app_settings as cfg

from .context import tenant_context, today_for
from .models import Business

NO_DATA_BODY = {"code": "no_data", "message": "Avval jadvallaringizni ulang."}


class NoData(APIException):
    status_code = 409
    default_code = "no_data"

    def __init__(self) -> None:
        super().__init__(detail=dict(NO_DATA_BODY))


def has_synced_source(b: Business) -> bool:
    from apps.integrations.models import DataSource

    return bool(
        DataSource.unscoped.filter(business=b, confirmed=True, last_synced_at__isnull=False)
        .exclude(status=DataSource.Status.PAUSED)
        .exists()
    )


def history_days(b: Business) -> int:
    from apps.finance.models import Transaction

    with tenant_context(b):
        first = Transaction.objects.filter(is_actual=True).aggregate(d=Min("txn_date"))["d"]
    return 0 if first is None else (today_for(b) - first).days + 1


def data_status(b: Business | None) -> str:
    if b is None:
        return "no_data"
    if b.is_demo:
        return "ok"
    if not has_synced_source(b):
        return "no_data"
    return "short_history" if history_days(b) < cfg.MIN_HISTORY_DAYS else "ok"


def onboarding_step(b: Business | None) -> str:
    from apps.integrations.models import DataSource

    if b is None or not b.profile_completed:
        return "business"
    if b.is_demo:
        return "done"
    qs = DataSource.unscoped.filter(business=b)
    if not qs.exists():
        return "connect"
    if not qs.filter(confirmed=True).exists():
        return "review"
    if not qs.filter(confirmed=True, last_synced_at__isnull=False).exists():
        return "analyzing"
    return "done"


def require_data(b: Business) -> None:
    if data_status(b) == "no_data":
        raise NoData


def status_payload(b: Business | None) -> dict[str, Any]:
    st = data_status(b)
    return {
        "onboarding_step": onboarding_step(b),
        "data_status": st,
        "history_days": history_days(b) if b is not None and st != "no_data" else 0,
    }

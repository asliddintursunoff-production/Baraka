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


class NeedsReview(APIException):
    status_code = 409
    default_code = "needs_review"

    def __init__(self, b: Business) -> None:
        super().__init__(detail=review_body(b))


def review_body(b: Business) -> dict[str, Any]:
    q = b.data_quality or {}
    from apps.ingestion.quality import summary_line

    return {
        "code": "needs_review",
        "message": summary_line(q) or "Ma'lumotni tekshirish kerak.",
        "recon": [r for r in q.get("recon", []) if not r.get("ok")][:8],
        "flags": q.get("flags", []),
    }


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
    """no_data | needs_review | short_history | ok (demo businesses are always ok)."""
    if b is None:
        return "no_data"
    if b.is_demo:
        return "ok"
    if not has_synced_source(b):
        return "no_data"
    q = b.data_quality or {}
    days = history_days(b)
    if q.get("status") == "no_data" or days == 0:
        return "no_data"  # e.g. an empty template: no numbers anywhere
    if q.get("status") == "needs_review":
        return "needs_review"  # does not reconcile / implausible: no forecasts, no advice
    return "short_history" if days < cfg.MIN_HISTORY_DAYS else "ok"


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


def stale_banner(q: dict[str, Any]) -> str:
    """Banner text when the data is more than 3 days old ("Ma'lumot 21 kun eski …")."""
    from datetime import date

    from apps.ai import uz_format as uz

    if not q.get("stale") or int(q.get("missing_days") or 0) <= 3 or not q.get("last_date"):
        return ""
    last = date.fromisoformat(q["last_date"])
    gap_from = date.fromisoformat(q["missing_from"])
    month = uz.MONTHS[gap_from.month - 1].capitalize()
    return (
        f"Ma'lumot {q['missing_days']} kun eski (oxirgisi {uz.format_date(last)} {last.year}). "
        f"{month} hisobotlarini kiriting — prognoz aniqroq bo'ladi."
    )


def require_data(b: Business) -> None:
    st = data_status(b)
    if st == "no_data":
        raise NoData
    if st == "needs_review":
        raise NeedsReview(b)


def status_payload(b: Business | None) -> dict[str, Any]:
    st = data_status(b)
    q = (b.data_quality or {}) if b is not None and not b.is_demo else {}
    return {
        "onboarding_step": onboarding_step(b),
        "data_status": st,
        "history_days": history_days(b) if b is not None and st != "no_data" else 0,
        "freshness": (
            {
                k: q.get(k)
                for k in ("as_of", "stale", "missing_from", "missing_to", "missing_days", "text")
            }
            | {"banner": stale_banner(q)}
        )
        if q.get("as_of")
        else None,
    }

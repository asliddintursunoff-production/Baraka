"""The current business for this request / job. Every tenant-scoped query reads it."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .models import Business

_current: ContextVar[int | None] = ContextVar("current_business_id", default=None)


class TenantContextMissing(RuntimeError):
    """A tenant-scoped query ran without a current business (use .unscoped explicitly)."""


def current_business_id() -> int | None:
    return _current.get()


def require_business_id() -> int:
    bid = _current.get()
    if bid is None:
        raise TenantContextMissing("no current business: wrap the code in tenant_context()")
    return bid


@contextmanager
def tenant_context(business: Business | int) -> Iterator[None]:
    bid = business if isinstance(business, int) else business.pk
    token = _current.set(bid)
    try:
        yield
    finally:
        _current.reset(token)


def today_for(business: Business) -> date:
    """The single source of "today": the real date in the business's time zone."""
    return datetime.now(ZoneInfo(business.timezone)).date()

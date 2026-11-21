"""Puts the session's business into the tenant context for the request.

The business comes only from the session (validated against Membership), never from
request data. Streaming responses must capture `request.business` themselves, because
the context is reset when the middleware returns.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.http import HttpRequest, HttpResponseBase

from .context import tenant_context
from .models import Business, Membership

SESSION_KEY = "business_id"


def resolve_business(user: Any, wanted: int | None) -> Business | None:
    if user is None or not user.is_authenticated:
        return None
    qs = Membership.objects.select_related("business").filter(user=user)
    if wanted is not None:
        m = qs.filter(business_id=wanted).first()
        if m is not None:
            return m.business
    m = qs.order_by("created_at", "id").first()
    return m.business if m else None


class TenantMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response: Callable[[HttpRequest], Any]) -> None:
        self.get_response = get_response
        self._async = iscoroutinefunction(get_response)
        if self._async:
            markcoroutinefunction(self)

    def __call__(self, request: HttpRequest) -> Any:
        if self._async:
            return self.__acall__(request)
        business = resolve_business(request.user, request.session.get(SESSION_KEY))
        request.business = business  # type: ignore[attr-defined]
        if business is None:
            return self.get_response(request)
        with tenant_context(business):
            return self.get_response(request)

    async def __acall__(self, request: HttpRequest) -> HttpResponseBase:
        user = await request.auser()
        wanted = await request.session.aget(SESSION_KEY)
        business = await sync_to_async(resolve_business)(user, wanted)
        request.business = business  # type: ignore[attr-defined]
        get_response: Callable[[HttpRequest], Awaitable[HttpResponseBase]] = self.get_response
        if business is None:
            return await get_response(request)
        with tenant_context(business):
            return await get_response(request)

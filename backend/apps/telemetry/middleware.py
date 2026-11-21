"""Adds a `Server-Timing` header (db / engine / llm / embed / total) to every response."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpRequest, HttpResponseBase

from . import timing


class ServerTimingMiddleware:
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
        bucket = timing.start_request()
        t0 = time.perf_counter()
        response: HttpResponseBase = self.get_response(request)
        return self._finish(response, bucket, t0)

    async def __acall__(self, request: HttpRequest) -> HttpResponseBase:
        bucket = timing.start_request()
        t0 = time.perf_counter()
        get_response: Callable[[HttpRequest], Awaitable[HttpResponseBase]] = self.get_response
        response = await get_response(request)
        return self._finish(response, bucket, t0)

    @staticmethod
    def _finish(
        response: HttpResponseBase, bucket: dict[str, float], t0: float
    ) -> HttpResponseBase:
        if not response.streaming:
            total = (time.perf_counter() - t0) * 1000
            response["Server-Timing"] = timing.format_header(bucket, total)
        return response

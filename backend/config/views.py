"""Health check and the single-page-app shell (index.html with injected APP_NAME)."""

from __future__ import annotations

import html
import json
from functools import lru_cache

from django.conf import settings
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

APP_CONFIG_TAG = '<script src="/app-config.js"></script>'


def app_config() -> dict[str, str]:
    return {"appName": settings.APP_NAME}


def _app_config_js() -> str:
    payload = json.dumps(app_config(), ensure_ascii=False).replace("<", "\\u003c")
    return f"window.__APP_CONFIG__ = {payload};"


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    body: dict[str, object] = {"ok": True, "app": settings.APP_NAME}
    if request.GET.get("deep") == "1":  # Railway healthcheck: also proves the DB answers
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        body["db"] = True
    return JsonResponse(body)


@require_GET
@ensure_csrf_cookie
def app_config_js(request: HttpRequest) -> HttpResponse:
    """Dev only path (Vite proxies it); production inlines the same script in index.html."""
    return HttpResponse(_app_config_js(), content_type="application/javascript; charset=utf-8")


def _read_index() -> str | None:
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return None
    raw = index.read_text(encoding="utf-8")
    raw = raw.replace(APP_CONFIG_TAG, f"<script>{_app_config_js()}</script>")
    start, end = raw.find("<title>"), raw.find("</title>")
    if start != -1 and end != -1:
        raw = raw[: start + 7] + html.escape(settings.APP_NAME) + raw[end:]
    return raw


_cached_index = lru_cache(maxsize=1)(_read_index)


@require_GET
@ensure_csrf_cookie
def spa(request: HttpRequest) -> HttpResponse:
    page = _read_index() if settings.DEBUG else _cached_index()  # dev: re-read each time
    if page is None:
        return HttpResponse(
            "<!doctype html><meta charset=utf-8><title>"
            + html.escape(settings.APP_NAME)
            + "</title><p>Frontend build topilmadi. <code>make dev</code> bilan "
            "<a href='http://localhost:5173'>localhost:5173</a> ni oching yoki "
            "<code>npm --prefix frontend run build</code> ni ishga tushiring.</p>",
            status=503,
        )
    response = HttpResponse(page)
    response["Cache-Control"] = "no-cache"
    return response

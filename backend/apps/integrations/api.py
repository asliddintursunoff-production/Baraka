"""Google OAuth endpoints (drive.file only) and Picker config. Tokens never reach the browser
except a short-lived access token for the Picker."""

from __future__ import annotations

import logging
import time
from urllib.parse import quote, urlencode

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_GET
from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import tenant_context
from config import app_settings as cfg

from . import google
from .models import DataSource, GoogleCredential

log = logging.getLogger(__name__)
SESSION_KEY = "google_oauth"
CONNECT = "/onboarding/connect"
ERRORS = {
    "access_denied": "Ruxsat berilmadi. Jadvallaringizni ulash uchun Google oynasida «Davom etish» tugmasini bosing.",
    "invalid_state": "Ulanish muddati o'tdi yoki sahifa almashdi. Qaytadan urinib ko'ring.",
    "exchange_failed": "Google bilan ulanishda xato bo'ldi. Bir daqiqadan keyin qaytadan urinib ko'ring.",
    "not_configured": "Google ulanishi sozlanmagan (Client ID yo'q).",
}


def _safe_next(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return f"{CONNECT}?step=pick"


def _error_redirect(code: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(
        f"{CONNECT}?{urlencode({'error': code, 'message': ERRORS[code]}, quote_via=quote)}"
    )


class GoogleStatusView(BusinessAPIView):
    def get(self, request: Request) -> Response:
        cred = GoogleCredential.objects.first()
        return Response(
            {
                "connected": cred is not None,
                "email": cred.email if cred else None,
                "needs_reauth": DataSource.objects.filter(status=DataSource.Status.REAUTH).exists(),
                "configured": google.configured(),
            }
        )


@require_GET
def google_start(request: HttpRequest) -> HttpResponse:
    business = getattr(request, "business", None)
    if not request.user.is_authenticated or business is None:
        return HttpResponseRedirect("/login")
    if not google.configured():
        return _error_redirect("not_configured")
    with tenant_context(business):
        has_refresh = (
            GoogleCredential.objects.exists()
            and not DataSource.objects.filter(status=DataSource.Status.REAUTH).exists()
        )
    started = google.start_auth(has_refresh_token=has_refresh)
    request.session[SESSION_KEY] = {
        "state": started.state,
        "verifier": started.code_verifier,
        "business_id": business.pk,
        "next": _safe_next(request.GET.get("next")),
        "ts": time.time(),
    }
    return HttpResponseRedirect(started.url)


@require_GET
def google_callback(request: HttpRequest) -> HttpResponse:
    business = getattr(request, "business", None)
    if not request.user.is_authenticated or business is None:
        return HttpResponseRedirect("/login")
    saved = request.session.pop(SESSION_KEY, None)  # single use
    if request.GET.get("error"):
        return _error_redirect("access_denied")
    state = request.GET.get("state", "")
    if (
        not saved
        or not state
        or state != saved.get("state")
        or saved.get("business_id") != business.pk
        or time.time() - float(saved.get("ts", 0)) > cfg.OAUTH_STATE_TTL_S
    ):
        return _error_redirect("invalid_state")
    try:
        tokens = google.exchange_code(
            request.GET.get("code", ""), state=state, code_verifier=saved.get("verifier")
        )
        google.store_tokens(business, tokens)
    except Exception as exc:
        log.warning("google token exchange failed: %s", type(exc).__name__)
        return _error_redirect("exchange_failed")
    with tenant_context(business):
        audit(f"user:{request.user.pk}", "google_connected", args={"email": tokens.email})
    return HttpResponseRedirect(_safe_next(saved.get("next")))


class PickerConfigView(BusinessAPIView):
    def get(self, request: Request) -> Response:
        from django.conf import settings

        try:
            token, expires = google.access_token(self.business)
        except google.ReauthRequired:
            return Response(
                {"error": "reauth_required", "message": "Google hisobini qayta ulang."}, status=409
            )
        return Response(
            {
                "access_token": token,
                "developer_key": settings.GOOGLE_PICKER_API_KEY,
                "app_id": google.app_id(),
                "expires_at": expires.isoformat(),
            }
        )


class GoogleDisconnectView(BusinessAPIView):
    def post(self, request: Request) -> Response:
        google.revoke(self.business)
        audit(f"user:{request.user.pk}", "google_disconnected")
        return Response({"ok": True})


def no_google_yet(request: HttpRequest) -> JsonResponse:  # pragma: no cover
    return JsonResponse({"ok": False}, status=404)

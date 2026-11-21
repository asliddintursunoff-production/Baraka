"""Google OAuth (drive.file only), credentials per business, Drive/Sheets API clients.

The refresh token is stored Fernet-encrypted per business and never leaves the backend.
Access tokens are minted on demand and cached in memory until shortly before expiry.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.tenancy.context import tenant_context
from apps.tenancy.models import Business
from config import app_settings as cfg

from .crypto import decrypt, encrypt
from .models import DataSource, GoogleCredential

log = logging.getLogger(__name__)

# oauthlib flags (OAUTHLIB_INSECURE_TRANSPORT / OAUTHLIB_RELAX_TOKEN_SCOPE) are set in settings.py

TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105 (public endpoint)
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class GoogleError(RuntimeError):
    pass


class ReauthRequired(GoogleError):
    pass


class NoAccess(GoogleError):
    pass


def redirect_uri() -> str:
    return settings.APP_URL + cfg.GOOGLE_CALLBACK_PATH


def client_config() -> dict[str, Any]:
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": [redirect_uri()],
        }
    }


def configured() -> bool:
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def app_id() -> str:
    """Picker appId = the Cloud project number = digits before '-' in the client id."""
    return settings.GOOGLE_OAUTH_CLIENT_ID.split("-", 1)[0]


# --- OAuth flow ------------------------------------------------------------------------
@dataclass(frozen=True)
class StartedAuth:
    url: str
    state: str
    code_verifier: str | None


def start_auth(*, has_refresh_token: bool) -> StartedAuth:
    from google_auth_oauthlib.flow import Flow

    state = secrets.token_urlsafe(32)
    flow = Flow.from_client_config(client_config(), scopes=list(cfg.GOOGLE_SCOPES), state=state)
    flow.redirect_uri = redirect_uri()
    params: dict[str, str] = {"access_type": "offline", "include_granted_scopes": "true"}
    if not has_refresh_token:
        params["prompt"] = "consent"  # only when we need a (new) refresh token
    url, _ = flow.authorization_url(**params)
    return StartedAuth(url=url, state=state, code_verifier=getattr(flow, "code_verifier", None))


@dataclass(frozen=True)
class ExchangedTokens:
    refresh_token: str | None
    access_token: str
    expiry: datetime | None
    email: str
    scopes: str


def exchange_code(code: str, *, state: str, code_verifier: str | None) -> ExchangedTokens:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(client_config(), scopes=list(cfg.GOOGLE_SCOPES), state=state)
    flow.redirect_uri = redirect_uri()
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    email = ""
    if getattr(creds, "id_token", None):
        info = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            creds.id_token, Request(), settings.GOOGLE_OAUTH_CLIENT_ID
        )
        email = str(info.get("email", ""))
    return ExchangedTokens(
        refresh_token=creds.refresh_token,
        access_token=str(creds.token),
        expiry=creds.expiry,
        email=email,
        scopes=" ".join(creds.scopes or cfg.GOOGLE_SCOPES),
    )


def store_tokens(business: Business, tok: ExchangedTokens) -> GoogleCredential:
    with tenant_context(business), transaction.atomic():
        cred: GoogleCredential | None = GoogleCredential.objects.select_for_update().first()
        if tok.refresh_token:
            enc = encrypt(tok.refresh_token)
        elif cred is not None:
            enc = cred.encrypted_refresh_token  # Google only sends it on consent
        else:
            raise GoogleError("Google refresh token bermadi")
        if cred is None:
            cred = GoogleCredential.objects.create(
                business=business, encrypted_refresh_token=enc, scopes=tok.scopes, email=tok.email
            )
        else:
            cred.encrypted_refresh_token, cred.scopes = enc, tok.scopes
            cred.email = tok.email or cred.email
            cred.save()
        DataSource.objects.filter(status=DataSource.Status.REAUTH).update(
            status=DataSource.Status.ACTIVE, last_error=""
        )
    _token_cache.pop(business.pk, None)
    if tok.expiry:
        _token_cache[business.pk] = (tok.access_token, tok.expiry.replace(tzinfo=UTC).timestamp())
    return cred


# --- access tokens --------------------------------------------------------------------
_token_cache: dict[int, tuple[str, float]] = {}
_lock = threading.Lock()


def has_credential(business: Business) -> bool:
    with tenant_context(business):
        return GoogleCredential.objects.exists()


def _mark_reauth(business: Business, message: str) -> None:
    with tenant_context(business):
        DataSource.objects.exclude(status=DataSource.Status.PAUSED).update(
            status=DataSource.Status.REAUTH, last_error=message
        )


def credentials(business: Business) -> Any:
    """google.oauth2.credentials.Credentials with a fresh access token."""
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    with tenant_context(business):
        cred = GoogleCredential.objects.first()
    if cred is None:
        raise ReauthRequired("Google hisob ulanmagan")
    cached = _token_cache.get(business.pk)
    c = Credentials(  # type: ignore[no-untyped-call]
        token=cached[0] if cached and cached[1] - time.time() > 120 else None,
        refresh_token=decrypt(cred.encrypted_refresh_token),
        token_uri=TOKEN_URI,
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=list(cfg.GOOGLE_SCOPES),
    )
    if not c.token:
        try:
            with _lock:
                c.refresh(Request())  # type: ignore[no-untyped-call]
        except RefreshError as exc:
            if "invalid_grant" in str(exc):
                _mark_reauth(business, "Google ruxsati bekor qilingan. Qayta ulang.")
                raise ReauthRequired("invalid_grant") from exc
            raise GoogleError("token refresh failed") from exc
        expiry = c.expiry.replace(tzinfo=UTC).timestamp() if c.expiry else time.time() + 3000
        _token_cache[business.pk] = (str(c.token), expiry)
    return c


def access_token(business: Business) -> tuple[str, datetime]:
    credentials(business)
    token, exp = _token_cache[business.pk]
    return token, datetime.fromtimestamp(exp, UTC)


def revoke(business: Business) -> None:
    import requests

    with tenant_context(business):
        cred = GoogleCredential.objects.first()
        if cred is None:
            return
        try:
            requests.post(
                REVOKE_URI, params={"token": decrypt(cred.encrypted_refresh_token)}, timeout=10
            )
        except Exception as exc:  # revoke is best effort; the token is deleted anyway
            log.info("google revoke failed: %s", type(exc).__name__)
        cred.delete()
        DataSource.objects.update(status=DataSource.Status.PAUSED)
    _token_cache.pop(business.pk, None)


# --- API calls with backoff -----------------------------------------------------------
def call[T](fn: Callable[[], T]) -> T:
    """Execute a googleapiclient request with exponential backoff on 429/5xx."""
    from googleapiclient.errors import HttpError

    for attempt in range(cfg.GOOGLE_BACKOFF_ATTEMPTS):
        try:
            return fn()
        except HttpError as exc:
            status = int(getattr(exc.resp, "status", 0))
            if status in (403, 404):
                raise NoAccess(f"no access ({status})") from exc
            if status in RETRY_STATUSES and attempt < cfg.GOOGLE_BACKOFF_ATTEMPTS - 1:
                time.sleep(0.5 * 2**attempt)
                continue
            raise GoogleError(f"google api error {status}") from exc
    raise GoogleError("unreachable")


def drive_service(business: Business) -> Any:
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=credentials(business), cache_discovery=False)


def sheets_service(business: Business) -> Any:
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=credentials(business), cache_discovery=False)


def file_meta(business: Business, file_id: str) -> dict[str, Any]:
    svc = drive_service(business)
    meta: dict[str, Any] = call(
        lambda: (
            svc.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,modifiedTime,owners(emailAddress)",
                supportsAllDrives=True,
            )
            .execute()
        )
    )
    return meta

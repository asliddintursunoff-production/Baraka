"""Django settings. Reads exactly the 8 env vars listed in `.env.example` (spec §3)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_DIR = BASE_DIR.parent

ENV_KEYS = (
    "APP_NAME",
    "APP_URL",
    "DEBUG",
    "DJANGO_SECRET_KEY",
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
)


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: only the 8 known keys; real env vars win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in ENV_KEYS:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_dotenv(REPO_DIR / ".env")


def _env(key: str, default: str = "") -> str:
    assert key in ENV_KEYS, f"{key} is not one of the 8 allowed env vars"
    return os.environ.get(key, default)


def _parse_database_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL must be a postgres:// URL")
    query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
    options: dict[str, object] = {
        # psycopg 3 connection pool (Django >= 5.1). Requires CONN_MAX_AGE = 0.
        "pool": {"min_size": 2, "max_size": 10, "timeout": 10},
    }
    if "sslmode" in query:
        options["sslmode"] = query["sslmode"]
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or 5432),
        "CONN_MAX_AGE": 0,
        "OPTIONS": options,
    }


APP_NAME = _env("APP_NAME", "BizPilot AI") or "BizPilot AI"
APP_URL = (_env("APP_URL", "http://localhost:8000") or "http://localhost:8000").rstrip("/")
DEBUG = _env("DEBUG", "false").lower() in ("1", "true", "yes", "on")
SECRET_KEY = _env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-insecure-secret-key-change-me"  # noqa: S105 - local dev only
    else:
        raise RuntimeError("DJANGO_SECRET_KEY is required when DEBUG is false")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GOOGLE_OAUTH_CLIENT_ID = _env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = _env("GOOGLE_OAUTH_CLIENT_SECRET")

_app_host = urlparse(APP_URL).hostname or "localhost"
ALLOWED_HOSTS = [_app_host]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]", "0.0.0.0"]  # noqa: S104
# Railway's internal healthcheck uses this host header.
ALLOWED_HOSTS.append("healthcheck.railway.app")
CSRF_TRUSTED_ORIGINS = [APP_URL]
if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["http://localhost:5173", "http://127.0.0.1:5173"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.tenancy",
    "apps.integrations",
    "apps.ingestion",
    "apps.finance",
    "apps.insights",
    "apps.knowledge",
    "apps.ai",
    "apps.actions",
    "apps.telemetry",
]

MIDDLEWARE = [
    "apps.telemetry.middleware.ServerTimingMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": _parse_database_url(
        _env("DATABASE_URL", "postgres://bizpilot:bizpilot@localhost:5433/bizpilot")
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = False
USE_TZ = True  # timestamps stored in UTC

# --- Static: built React app served by WhiteNoise from the site root -------------
FRONTEND_DIST = REPO_DIR / "frontend" / "dist"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.is_dir() else None
WHITENOISE_INDEX_FILE = False


def _immutable_file_test(path: str, url: str) -> bool:
    # Vite emits content-hashed files under /assets/.
    return url.startswith("/assets/")


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable_file_test

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = APP_URL.startswith("https://")
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_HTTPONLY = False  # the SPA reads it to send X-CSRFToken
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # The Google SDKs can log request URLs; keep them quiet so keys never leak.
        "google_genai": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
        "httpx2": {"level": "WARNING"},
        "websockets": {"level": "WARNING"},
    },
}

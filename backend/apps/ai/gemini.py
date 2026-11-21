"""Gemini clients. The API key is read from settings only and never logged or returned."""

from __future__ import annotations

import warnings
from functools import lru_cache

from django.conf import settings
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

# Ephemeral tokens are marked experimental in the SDK; the warning is noise in logs.
warnings.filterwarnings("ignore", message=r".*ephemeral token.*", category=Warning)
warnings.filterwarnings("ignore", message=r".*token creation implementation.*", category=Warning)

HTTP_TIMEOUT_MS = 30_000
RETRYABLE_CODES = (429, 500, 502, 503, 504)
# One bounded retry policy (the SDK default is 5 attempts with up to 60 s backoff,
# far too slow for a chat answer budget of a few seconds).
RETRY = types.HttpRetryOptions(
    attempts=3,
    initial_delay=0.4,
    max_delay=2.0,
    exp_base=2,
    jitter=0.2,
    http_status_codes=list(RETRYABLE_CODES),
)


class GeminiNotConfigured(RuntimeError):
    pass


def _key() -> str:
    key: str = settings.GEMINI_API_KEY
    if not key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set")
    return key


@lru_cache(maxsize=1)
def client() -> genai.Client:
    """v1beta client: generate, embed and ephemeral Live auth tokens (see docs/AI_NOTES.md)."""
    return genai.Client(
        api_key=_key(),
        http_options=types.HttpOptions(
            api_version="v1beta", timeout=HTTP_TIMEOUT_MS, retry_options=RETRY
        ),
    )


def is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, genai_errors.APIError) and exc.code in RETRYABLE_CODES


def scrub(text: str) -> str:
    """Remove the API key from any text before it is logged or shown."""
    key = settings.GEMINI_API_KEY
    return text.replace(key, "***") if key else text

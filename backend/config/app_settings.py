"""Every non-secret application constant lives here (spec §3).

Only the 8 env vars from `.env.example` are read in `settings.py`; nothing in this
module comes from the environment.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

# --- AI models (verified by `manage.py check_ai`) ---------------------------------
AI_MODELS: dict[str, str] = {
    "chat": "gemini-3.8-flash",  # chat orchestrator, tool calling, structured output
    "light": "gemini-3.8-flash",  # STT, summary, rules (no flash-lite)
    "mapping": "gemini-3.8-flash",  # sheet column recognition (one-off)
    "live": "gemini-3.8-live",  # live voice (native audio)
    "embedding": "gemini-embedding-001",  # pgvector
}
# Chat fallback chain (approved 2026-11-21): on 429/503/504 or a passed deadline the next
# model is tried immediately; a model with 3 errors within 60 s is skipped for 60 s.
CHAT_MODEL_CHAIN = ("gemini-3.8-flash", "gemini-3.6-flash")  # owner 2026-11-22: no flash-lite
CHAT_THINKING_BY_MODEL: dict[str, str | None] = {
    "gemini-3.8-flash": "LOW",
    "gemini-3.6-flash": "LOW",
}
CHAT_ATTEMPT_DEADLINE_S = 12.0  # 3.8-flash takes 8-10 s; owner 2026-11-22: quality first
CIRCUIT_ERRORS = 3
CIRCUIT_WINDOW_S = 60.0
CIRCUIT_OPEN_S = 60.0
CHAT_CONTEXT_MAX_TOKENS = 2_000
TTS_MODEL = "gemini-3.8-flash-tts"
TTS_MODEL_CHAIN = (TTS_MODEL, "gemini-3.1-flash-tts-preview", "gemini-2.5-pro-preview-tts")
TTS_VOICE = "Kore"
# Used only by the M0 voice spike to synthesize Uzbek test questions.
SPIKE_TTS_MODEL = TTS_MODEL
EMBEDDING_DIM = 768  # output_dimensionality=768; vectors are L2-normalized before storing
CHAT_THINKING_LEVEL = "MEDIUM"  # quality first (MINIMAL rejected)
CHAT_MAX_TOOL_ROUNDS = 3

# --- Live voice ---------------------------------------------------------------------
LIVE_TOKEN_USES = 1
LIVE_TOKEN_TTL_MIN = 30  # session messages rejected after this
LIVE_NEW_SESSION_WINDOW_S = 600  # P3: a prefetched token stays usable for 10 min
LIVE_VOICE_NAME = "Kore"
LIVE_SILENCE_DURATION_MS = 800  # kitchens are noisy: don't cut the user off at short pauses
LIVE_PREFIX_PADDING_MS = 300  # speech must last >= 300 ms before it counts
LIVE_TRANSCRIPTION_LANGUAGE_HINTS = ["uz"]
LIVE_INPUT_RATE = 16_000
LIVE_OUTPUT_RATE = 24_000
LIVE_CONTEXT_MAX_TOKENS = 12_000  # full business digest goes into Live too (2026-11-22)

# --- Business defaults --------------------------------------------------------------
DEFAULT_TIMEZONE = "Asia/Tashkent"
DEFAULT_SAFE_MIN_BALANCE = Decimal("10000000.00")

# --- Forecast -----------------------------------------------------------------------
FORECAST_HORIZONS = (7, 30, 60, 90)
DEFAULT_HORIZON_DAYS = 60
HISTORY_WEEKS = 8
MIN_HISTORY_WEEKS = 2
SPEND_LIMIT_ROUNDING = Decimal("1000000")  # round down to 1 mln
INSTALLMENT_MONTHS = 3
P10_P90_Z = 1.2816  # standard-normal quantile for P10/P90

# --- Google (M5) ----------------------------------------------------------------------
GOOGLE_SCOPES = ("openid", "email", "https://www.googleapis.com/auth/drive.file")
GOOGLE_CALLBACK_PATH = "/api/integrations/google/callback"
OAUTH_STATE_TTL_S = 600
SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GOOGLE_BACKOFF_ATTEMPTS = 4

# --- Ingestion / scheduler ----------------------------------------------------------
SYNC_INTERVAL_MIN = 15
MAPPING_CONFIDENCE_THRESHOLD = 0.8
MAPPING_SAMPLE_ROWS = 20
DAILY_BRIEF_AT = time(8, 0)  # Asia/Tashkent
NIGHTLY_LEARNING_AT = time(3, 0)  # Asia/Tashkent

# --- Learning -----------------------------------------------------------------------
WEEKDAY_FACTOR_EWMA_ALPHA = 0.3
RULE_DUPLICATE_COSINE = 0.9
SEGMENT_MIN_BUSINESSES = 5
MEMORY_TOP_K = 6

# --- Tool envelope ------------------------------------------------------------------
TOOL_RESPONSE_MAX_BYTES = 2048

# --- AI budget (final mode, PLAN §0) ----------------------------------------------------
# dev = DEBUG=true: chat on the cheapest model only; demo = DEBUG=false: full fallback chain.
AI_PROFILES: dict[str, tuple[str, ...]] = {
    "dev": CHAT_MODEL_CHAIN,  # owner 2026-11-22: dev uses the demo models too
    "demo": CHAT_MODEL_CHAIN,
}
AI_DAILY_BUDGET_USD = Decimal("0.50")
AI_TOTAL_BUDGET_USD = Decimal("4.00")
# Owner 2026-11-22: "limit qo'yma, umuman" -> no blocking; every call is still logged.
AI_BUDGET_ENFORCED = False
# Estimated USD per 1M tokens (input, output); Live per minute of session. Estimates only.
AI_PRICES_PER_M_TOKENS: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-3.8-flash": (Decimal("0.50"), Decimal("3.00")),
    "gemini-3.6-flash": (Decimal("0.30"), Decimal("2.50")),
    "gemini-3.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
    "gemini-3.8-flash-tts": (Decimal("0.50"), Decimal("10.00")),
    "gemini-embedding-001": (Decimal("0.15"), Decimal("0")),
}
AI_LIVE_USD_PER_MIN = Decimal("0.025")
AI_DEFAULT_PRICE_PER_M = (Decimal("0.50"), Decimal("3.00"))
LIVE_MAX_SESSION_S = 300  # one Live session lasts 5 min at most
LIVE_RESERVE_S = 60  # billed at mint (tokens may go unused), corrected by /live/finish
LIVE_IDLE_CLOSE_S = 30
BUDGET_MESSAGE_LIVE = "Bugungi ovoz limiti tugadi"

# --- Alerts + brief (M6): templates only, never an LLM -----------------------------------
ALERT_HORIZON_DAYS = 30
DAILY_BRIEF_AT = time(8, 0)  # Asia/Tashkent

# --- Pricing (public /pricing page) --------------------------------------------------------
# Amounts are NOT decided yet: None renders the design's "[narx]" / "[N]" placeholder.
# Fill in real numbers here only; never in the frontend.
PRICING: dict[str, dict[str, int | None]] = {
    "trial": {
        "price_uzs": 0,
        "days": None,
        "sheets": None,
        "chat_per_day": None,
        "voice_minutes": None,
    },
    "business": {"price_uzs_month": None},
}
# --- "No data, no answer" ------------------------------------------------------------------
MIN_HISTORY_DAYS = 14  # under this: short_history (no forecasts or purchase decisions)

# --- Advisor mode (plans, goals, debts, loans, investments) ------------------------------
ADVISOR_MODEL_CHAIN = ("gemini-3.8-flash", "gemini-3.6-flash")
ADVISOR_THINKING_BY_MODEL: dict[str, str | None] = {
    "gemini-3.8-flash": "LOW",
    "gemini-3.6-flash": "LOW",
    "gemini-3.5-flash-lite": None,
}
ADVISOR_MAX_ROUNDS = 3  # owner 2026-11-22: latency
ADVISOR_ATTEMPT_DEADLINE_S = 20.0
ADVISOR_PLAN_MAX = 6

# --- Fayl tahlili (analyst) -----------------------------------------------------------------
# From models.list 2026-11-22: gemini-4-argon exists -> first; then 3.1-pro; then 3.8-flash.
AI_MODELS["analyst"] = "gemini-4-argon"
AI_ANALYST_CHAIN = ("gemini-3.8-flash", "gemini-3.1-pro-preview")  # simple questions: fast and good
# hard questions + "Fayl xulosasi": strongest that answered in tests (argon gave 504 on 2026-11-22)
AI_ANALYST_DEEP_CHAIN = ("gemini-3.1-pro-preview", "gemini-3.8-flash")
AI_ANALYST_THINKING: dict[str, str | None] = {"gemini-3.8-flash": "LOW"}
AI_ANALYST_DEEP_THINKING: dict[str, str | None] = {"gemini-3.8-flash": "HIGH"}
AI_ANALYST_DAILY_BUDGET_USD = 1_000_000.00  # effectively off (owner request 2026-11-22)
# Prices may change on 2026-12-01; keep them updated here.
AI_PRICES_PER_M_TOKENS.update(
    {
        "gemini-4-argon": (Decimal("2.00"), Decimal("12.00")),
        "gemini-3.1-pro-preview": (Decimal("2.00"), Decimal("12.00")),
    }
)

# --- Full-context chat (owner request 2026-11-22): one strong model call with the digest -----
CHAT_FULL_CHAIN = (
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
)  # owner 2026-11-22: MEDIUM thinking took ~1 min; LOW = 5-14 s with the same numbers
CHAT_FULL_DEADLINE_S = 15.0
CHAT_FULL_THINKING: dict[str, str | None] = {
    "gemini-3.8-flash": "LOW",
    "gemini-3-flash-preview": "LOW",
}

# --- DEMO mode (owner 2026-11-22, until the demo): only Q1–Q4 (+ side questions), zero LLM ----
# Catalogue + free chat stay in the code but are unreachable while this is True.
# Live = speech-to-text only; every spoken answer is a pre-recorded clip.
DEMO_GOLDEN_ONLY = True

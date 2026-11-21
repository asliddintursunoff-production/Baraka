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
    "light": "gemini-3.5-flash-lite",  # alert text, conversation summary, rule extraction
    "mapping": "gemini-3.8-flash",  # sheet column recognition (one-off)
    "live": "gemini-3.8-live",  # live voice (native audio)
    "embedding": "gemini-embedding-001",  # pgvector
}
# Chat fallback chain (approved 2026-11-21): on 429/503/504 or a passed deadline the next
# model is tried immediately; a model with 3 errors within 60 s is skipped for 60 s.
CHAT_MODEL_CHAIN = ("gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite")
CHAT_THINKING_BY_MODEL: dict[str, str | None] = {
    "gemini-3.8-flash": "LOW",
    "gemini-3.6-flash": "LOW",
    "gemini-3.5-flash-lite": None,
}
CHAT_ATTEMPT_DEADLINE_S = 5.0
CIRCUIT_ERRORS = 3
CIRCUIT_WINDOW_S = 60.0
CIRCUIT_OPEN_S = 60.0
CHAT_CONTEXT_MAX_TOKENS = 2_000
TTS_MODEL = "gemini-3.8-flash-tts"
TTS_VOICE = "Kore"
# Used only by the M0 voice spike to synthesize Uzbek test questions.
SPIKE_TTS_MODEL = TTS_MODEL
EMBEDDING_DIM = 768  # output_dimensionality=768; vectors are L2-normalized before storing
CHAT_THINKING_LEVEL = "LOW"  # lowest level 3.8-flash accepts (MINIMAL is rejected), see AI_NOTES
CHAT_MAX_TOOL_ROUNDS = 3

# --- Live voice ---------------------------------------------------------------------
LIVE_TOKEN_USES = 1
LIVE_TOKEN_TTL_MIN = 30  # session messages rejected after this
LIVE_NEW_SESSION_WINDOW_S = 60  # a new session must be opened within this window
LIVE_VOICE_NAME = "Kore"
LIVE_SILENCE_DURATION_MS = 500  # end-of-speech silence for server VAD (docs: 500-800)
LIVE_PREFIX_PADDING_MS = 100
LIVE_TRANSCRIPTION_LANGUAGE_HINTS = ["uz"]
LIVE_INPUT_RATE = 16_000
LIVE_OUTPUT_RATE = 24_000
LIVE_CONTEXT_MAX_TOKENS = 1_500

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

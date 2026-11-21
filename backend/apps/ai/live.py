"""Gemini Live: session config + ephemeral token minting.

The browser connects to Gemini Live directly with a short-lived, single-use token whose
model, system instruction, tools and audio settings are locked server-side. The API key
never leaves the backend. Facts behind each setting: docs/AI_NOTES.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from google.genai import types

from config import app_settings as cfg

from .gemini import client

ToolBehavior = Literal["blocking", "non_blocking"]


@dataclass(frozen=True)
class LiveToken:
    token: str
    model: str
    expires_at: datetime
    new_session_expires_at: datetime
    mint_ms: float


def function_declarations(
    specs: list[dict[str, Any]], behavior: ToolBehavior
) -> list[types.FunctionDeclaration]:
    """`specs` are registry entries: {name, description, parameters (JSON schema)}."""
    b = types.Behavior.BLOCKING if behavior == "blocking" else types.Behavior.NON_BLOCKING
    return [
        types.FunctionDeclaration(
            name=s["name"],
            description=s["description"],
            parameters_json_schema=s["parameters"],
            behavior=b,
        )
        for s in specs
    ]


def live_config(
    *,
    system_instruction: str,
    tool_specs: list[dict[str, Any]],
    behavior: ToolBehavior = "blocking",
    silence_ms: int = cfg.LIVE_SILENCE_DURATION_MS,
) -> types.LiveConnectConfig:
    """Config locked into the token. No thinking_config / proactivity / affective dialog:
    gemini-3.8-live rejects or ignores them (AI_NOTES §Live)."""
    transcription = types.AudioTranscriptionConfig(
        language_codes=list(cfg.LIVE_TRANSCRIPTION_LANGUAGE_HINTS)
    )
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=system_instruction,
        tools=[types.Tool(function_declarations=function_declarations(tool_specs, behavior))],
        input_audio_transcription=transcription,
        output_audio_transcription=transcription,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg.LIVE_VOICE_NAME)
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                silence_duration_ms=silence_ms,
                prefix_padding_ms=cfg.LIVE_PREFIX_PADDING_MS,
            )
        ),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
    )


def mint_token(config: types.LiveConnectConfig) -> LiveToken:
    """Single-use token. `lock_additional_fields=[]` locks exactly the fields set in
    `config`; session_resumption stays unlocked so the client can resume with a handle."""
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=cfg.LIVE_TOKEN_TTL_MIN)
    new_session_until = now + timedelta(seconds=cfg.LIVE_NEW_SESSION_WINDOW_S)
    t0 = time.perf_counter()
    token = client().auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=cfg.LIVE_TOKEN_USES,
            expire_time=expires,
            new_session_expire_time=new_session_until,
            live_connect_constraints=types.LiveConnectConstraints(
                model=cfg.AI_MODELS["live"], config=config
            ),
            lock_additional_fields=[],
        )
    )
    mint_ms = (time.perf_counter() - t0) * 1000
    if not token.name:
        raise RuntimeError("auth_tokens.create returned no token")
    return LiveToken(
        token=token.name,
        model=cfg.AI_MODELS["live"],
        expires_at=expires,
        new_session_expires_at=new_session_until,
        mint_ms=mint_ms,
    )

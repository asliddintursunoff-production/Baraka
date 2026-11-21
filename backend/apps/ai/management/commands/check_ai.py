"""`manage.py check_ai`: verify every model ID and the Live/embedding paths with the real key.

Exits non-zero with a clear message when a required model or capability is missing.
The API key is never printed (exceptions are scrubbed).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from google import genai
from google.genai import types

from apps.ai import spike
from apps.ai.gemini import client, is_retryable, scrub
from apps.ai.live import live_config, mint_token
from config import app_settings as cfg


class Command(BaseCommand):
    help = (
        "Check Gemini model IDs, chat/light/embedding calls and a Live session via ephemeral token."
    )

    def handle(self, *args: Any, **opts: Any) -> None:
        failures: list[str] = []
        warnings: list[str] = []

        def ok(label: str, detail: str = "") -> None:
            self.stdout.write(
                self.style.SUCCESS(f"  OK   {label}") + (f"  {detail}" if detail else "")
            )

        def fail(label: str, exc: BaseException | str) -> None:
            msg = scrub(str(exc))[:300]
            failures.append(f"{label}: {msg}")
            self.stdout.write(self.style.ERROR(f"  FAIL {label}  {msg}"))

        def warn(label: str, msg: str) -> None:
            warnings.append(f"{label}: {msg}")
            self.stdout.write(self.style.WARNING(f"  WARN {label}  {msg}"))

        c = client()

        # 1. Model IDs
        self.stdout.write("Model IDs (models.list):")
        try:
            available = {m.name.removeprefix("models/") for m in c.models.list() if m.name}
        except Exception as exc:
            raise CommandError(f"models.list failed: {scrub(str(exc))[:300]}") from None
        for role, model in cfg.AI_MODELS.items():
            if model in available:
                ok(f"{role:<9} {model}")
            else:
                fail(f"{role} {model}", "not available for this API key")
        if cfg.SPIKE_TTS_MODEL not in available:
            warn("spike tts", f"{cfg.SPIKE_TTS_MODEL} not available (voice spike only)")

        # 2. chat + light generate
        self.stdout.write("Generate:")
        for role in ("chat", "light"):
            model = cfg.AI_MODELS[role]
            conf = types.GenerateContentConfig(max_output_tokens=200)
            if role == "chat":
                conf.thinking_config = types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel(cfg.CHAT_THINKING_LEVEL)
                )
            t0 = time.perf_counter()
            try:
                r = c.models.generate_content(
                    model=model, contents="Faqat bitta so'z bilan javob ber: salom", config=conf
                )
                ok(
                    f"{role:<9} {model}",
                    f"{(time.perf_counter() - t0) * 1000:.0f} ms, {r.text!r:.40}",
                )
            except Exception as exc:
                fail(f"{role} generate", exc)

        # 2b. tools + structured output in one request (needed by the chat orchestrator, M3)
        try:
            r = c.models.generate_content(
                model=cfg.AI_MODELS["chat"],
                contents="Salom. Qisqa javob ber.",
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel(cfg.CHAT_THINKING_LEVEL)
                    ),
                    tools=[
                        types.Tool(
                            function_declarations=[
                                types.FunctionDeclaration(
                                    name="get_cash_status",
                                    description="Hozirgi kassa holati",
                                    parameters_json_schema={"type": "object", "properties": {}},
                                )
                            ]
                        )
                    ],
                    response_mime_type="application/json",
                    response_json_schema={
                        "type": "object",
                        "properties": {"headline": {"type": "string"}},
                        "required": ["headline"],
                    },
                ),
            )
            ok("chat tools+json", "function calling and response_json_schema accepted together")
        except Exception as exc:
            if is_retryable(exc):
                warn("chat tools+json", f"model busy, not verified ({scrub(str(exc))[:80]})")
            else:
                warn(
                    "chat tools+json", f"rejected ({scrub(str(exc))[:160]}); M3 will use two calls"
                )

        # 3. Embedding
        self.stdout.write("Embedding:")
        try:
            er = c.models.embed_content(
                model=cfg.AI_MODELS["embedding"],
                contents="Agro Go'shtga to'lov doim 15 kun keyin",
                config=types.EmbedContentConfig(
                    output_dimensionality=cfg.EMBEDDING_DIM, task_type="RETRIEVAL_DOCUMENT"
                ),
            )
            values = (er.embeddings or [types.ContentEmbedding()])[0].values or []
            if len(values) != cfg.EMBEDDING_DIM:
                fail("embedding dim", f"got {len(values)}, expected {cfg.EMBEDDING_DIM}")
            else:
                norm = float(np.linalg.norm(np.asarray(values)))
                ok(
                    "embedding",
                    f"dim={len(values)} raw L2 norm={norm:.3f} (normalized before storing)",
                )
        except Exception as exc:
            fail("embedding", exc)

        # 4. Live via ephemeral token
        self.stdout.write("Live (ephemeral token):")
        try:
            result = asyncio.run(self._live_check())
            ok("live", result)
        except Exception as exc:
            fail("live", exc)

        self.stdout.write("")
        if failures:
            raise CommandError("check_ai failed:\n  - " + "\n  - ".join(failures))
        self.stdout.write(
            self.style.SUCCESS("All AI checks passed.")
            + (f" ({len(warnings)} warning(s))" if warnings else "")
        )

    async def _live_check(self) -> str:
        conf = live_config(
            system_instruction="Faqat o'zbek tilida, bitta qisqa jumla bilan javob ber.",
            tool_specs=[spike.EVALUATE_PURCHASE_SPEC],
        )
        t0 = time.perf_counter()
        tok = await asyncio.to_thread(mint_token, conf)
        token_client = genai.Client(api_key=tok.token, http_options={"api_version": "v1beta"})
        t1 = time.perf_counter()
        async with token_client.aio.live.connect(
            model=tok.model,
            config=types.LiveConnectConfig(response_modalities=[types.Modality.AUDIO]),
        ) as session:
            t_ready = time.perf_counter()
            await session.send_realtime_input(text="Salom! Ishlayapsanmi?")
            t_sent = time.perf_counter()
            first_audio: float | None = None
            audio_bytes = 0
            transcript: list[str] = []
            async for msg in session.receive():
                sc = msg.server_content
                if sc and sc.model_turn and sc.model_turn.parts:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            first_audio = first_audio or time.perf_counter()
                            audio_bytes += len(part.inline_data.data)
                if sc and sc.output_transcription and sc.output_transcription.text:
                    transcript.append(sc.output_transcription.text)
                if sc and sc.turn_complete:
                    break
        if not first_audio:
            raise RuntimeError("Live session returned no audio")
        return (
            f"token {tok.mint_ms:.0f} ms, connect {(t_ready - t1) * 1000:.0f} ms, "
            f"text->first audio {(first_audio - t_sent) * 1000:.0f} ms, "
            f"{audio_bytes / 48000:.1f} s audio, total {(time.perf_counter() - t0):.1f} s, "
            f"says: {''.join(transcript).strip()[:60]!r}"
        )

"""`manage.py voice_spike`: automated M0 voice test against gemini-3.8-live.

For each of 10 Uzbek questions (some numeric, some with Russian words mixed in):
  1. synthesize the question with the TTS model (cached in spike_out/),
  2. mint an ephemeral token (same config as /dev/voice) and open a Live session with it,
  3. stream the audio as 20 ms PCM16 frames at real-time pace, then low-level noise
     (like an open mic), so the server's own VAD decides when the user stopped,
  4. answer tool calls with the fixed fake `evaluate_purchase`,
  5. record: session ready, speech_end -> first audio, tool round trip, transcripts,
     and save the model's audio to spike_out/*.wav for listening.
Results go to spike_out/results_<mode>.json; docs/LATENCY.md summarizes them.
"""

from __future__ import annotations

import asyncio
import json
import time
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from google import genai
from google.genai import types

from apps.ai import budget, spike, uz_format
from apps.ai.gemini import client, scrub
from apps.ai.live import live_config, mint_token
from apps.ai.prompts import live_system_instruction
from config import app_settings as cfg

OUT = Path(settings.BASE_DIR) / "spike_out"
FRAME_MS = 20
IN_RATE = 16_000
FRAME_SAMPLES = IN_RATE * FRAME_MS // 1000
TURN_TIMEOUT_S = 30

QUESTIONS: list[dict[str, Any]] = [
    {
        "q": "Hozir kassamda qancha pul bor?",
        "expect": ["qirq sakkiz million ikki yuz ming"],
        "tool": False,
    },
    {
        "q": "Yigirma besh million so'mga yangi jihoz olsam, keyingi oy oylik va kreditga pulim yetadimi?",
        "expect": ["olti million ikki yuz ming", "o'ninchi dekabr", "o'n ikkinchi yanvar"],
        "tool": True,
    },
    {
        "q": "25 millionga jihoz olsam, oylikka yetadimi?",
        "expect": ["olti million ikki yuz ming", "o'ninchi dekabr", "o'n ikkinchi yanvar"],
        "tool": True,
    },
    {
        "q": "Slushay, yigirma besh millionga oborudovaniye olsam, zarplataga yetadimi?",
        "expect": ["olti million ikki yuz ming", "o'ninchi dekabr", "o'n ikkinchi yanvar"],
        "tool": True,
    },
    {
        "q": "Eng qiyin kun qachon va o'sha kuni kassada qancha qoladi?",
        "expect": ["o'ninchi dekabr", "o'n sakkiz million sakkiz yuz ming"],
        "tool": False,
    },
    {
        "q": "Kredit to'lovi qachon va qancha?",
        "expect": ["o'ninchi dekabr", "o'n sakkiz million besh yuz ming"],
        "tool": False,
    },
    {
        "q": "Jihozni uch oyga bo'lib to'lasam bo'ladimi? Narxi yigirma besh million.",
        "expect": ["to'qqiz million sakkiz yuz ming"],
        "tool": True,
    },
    {
        "q": "Kassada qirq sakkiz million turibdi, normalno. O'n millionlik remont qilsam bo'ladimi?",
        "expect": [],
        "tool": True,
    },
    {"q": "O'tgan oy qancha foyda qildim?", "expect": ["jadvalingizda yo'q"], "tool": False},
    {"q": "Ertaga ob-havo qanday bo'ladi?", "expect": [], "tool": False},
]


@dataclass
class TurnResult:
    idx: int
    question: str
    mode: str
    ok: bool = False
    error: str = ""
    mint_ms: float = 0
    connect_ms: float = 0
    session_ready_ms: float = 0
    speech_end_to_first_audio_ms: float | None = None
    tool_called: bool = False
    tool_args: dict[str, Any] = field(default_factory=dict)
    speech_end_to_tool_call_ms: float | None = None
    tool_exec_ms: float | None = None
    tool_response_to_first_audio_ms: float | None = None
    speech_end_to_answer_audio_ms: float | None = None
    interrupted: int = 0
    heard: str = ""
    said: str = ""
    audio_s: float = 0
    expect_hits: dict[str, bool] = field(default_factory=dict)
    cyrillic_in_answer: bool = False
    pause_ms: int = 0
    pause_at_s: float | None = None
    cut_off: bool = False  # the model answered (audio or tool call) before the user finished


def insert_pause(audio: np.ndarray, pause_ms: int, seed: int) -> tuple[np.ndarray, float]:
    """Insert a mid-sentence "thinking" pause at the quietest word gap in the middle third."""
    frames = len(audio) // FRAME_SAMPLES
    rms = np.array(
        [
            np.sqrt(
                np.mean(audio[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES].astype(np.float64) ** 2)
            )
            for i in range(frames)
        ]
    )
    voiced = np.flatnonzero(rms > 500)
    lo, hi = voiced[0], voiced[-1]
    a, b = lo + (hi - lo) // 3, lo + 2 * (hi - lo) // 3
    window = np.convolve(rms, np.ones(5) / 5, mode="same")
    cut = int(a + np.argmin(window[a:b]))
    noise = (np.random.default_rng(seed).standard_normal(IN_RATE * pause_ms // 1000) * 30).astype(
        np.int16
    )
    at = cut * FRAME_SAMPLES
    return np.concatenate([audio[:at], noise, audio[at:]]), at / IN_RATE


def _lowpass_resample_24k_to_16k(pcm24: np.ndarray) -> np.ndarray:
    x = pcm24.astype(np.float64)
    # windowed-sinc low-pass at 7.2 kHz (anti-alias for 16 kHz), then interpolate
    taps = 63
    n = np.arange(taps) - (taps - 1) / 2
    fc = 7200 / 24000
    h = np.sinc(2 * fc * n) * np.hamming(taps)
    h /= h.sum()
    y = np.convolve(x, h, mode="same")
    t_out = np.arange(0, len(y) * 2 // 3) * 1.5
    z = np.interp(t_out, np.arange(len(y)), y)
    out: np.ndarray = np.clip(z, -32768, 32767).astype(np.int16)
    return out


def _write_wav(path: Path, pcm: bytes, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


class Command(BaseCommand):
    help = "Automated Uzbek voice spike against Gemini Live (latency + quality)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--behavior", choices=["blocking", "non_blocking"], default="blocking")
        parser.add_argument("--scheduling", choices=["WHEN_IDLE", "INTERRUPT"], default="WHEN_IDLE")
        parser.add_argument("--only", type=str, default="", help="comma-separated 1-based indexes")
        parser.add_argument(
            "--tool-only", action="store_true", help="only questions that need the tool"
        )
        parser.add_argument(
            "--variant",
            choices=["base", "answer"],
            default="base",
            help="answer: tool returns a ready-made speech.answer sentence (measurement only)",
        )
        parser.add_argument("--silence-ms", type=int, default=cfg.LIVE_SILENCE_DURATION_MS)
        parser.add_argument(
            "--pause-ms", type=int, default=0, help="insert a mid-sentence thinking pause (P2 test)"
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        OUT.mkdir(exist_ok=True)
        mode = opts["behavior"] + (
            "" if opts["behavior"] == "blocking" else f"_{opts['scheduling']}"
        )
        if opts["variant"] != "base":
            mode += f"_{opts['variant']}"
        if opts["silence_ms"] != cfg.LIVE_SILENCE_DURATION_MS:
            mode += f"_sil{opts['silence_ms']}"
        if opts["pause_ms"]:
            mode += f"_pause{opts['pause_ms']}"
        self.pause_ms: int = opts["pause_ms"]
        self.variant: str = opts["variant"]
        self.silence_ms: int = opts["silence_ms"]
        picks = [int(i) for i in opts["only"].split(",") if i.strip()] or list(range(1, 11))
        if opts["tool_only"]:
            picks = [i for i in picks if QUESTIONS[i - 1]["tool"]]
        results: list[TurnResult] = []
        for i in picks:
            item = QUESTIONS[i - 1]
            self.stdout.write(f"[{mode}] Q{i}: {item['q']}")
            try:
                audio = self._question_audio(i, item["q"])
                pause_at = None
                if self.pause_ms:
                    audio, pause_at = insert_pause(audio, self.pause_ms, seed=i)
                res = asyncio.run(
                    asyncio.wait_for(
                        self._run_turn(i, item, audio, opts["behavior"], opts["scheduling"], mode),
                        timeout=TURN_TIMEOUT_S + 30,
                    )
                )
            except Exception as exc:
                res = TurnResult(idx=i, question=item["q"], mode=mode, error=scrub(repr(exc))[:300])
            res.pause_ms, res.pause_at_s = self.pause_ms, pause_at
            results.append(res)
            self.stdout.write(
                f"   ok={res.ok} ready={res.session_ready_ms:.0f} first_audio={res.speech_end_to_first_audio_ms} "
                f"tool={res.tool_called} answer_audio={res.speech_end_to_answer_audio_ms} "
                f"cut_off={res.cut_off} interrupted={res.interrupted} err={res.error[:80]}"
            )
            self.stdout.write(f"   heard: {res.heard}")
            self.stdout.write(f"   said : {res.said}")
        path = OUT / f"results_{mode}_{time.strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(
            json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=1), encoding="utf-8"
        )
        self.stdout.write(self.style.SUCCESS(f"saved {path}"))

    # --- audio ------------------------------------------------------------------------
    def _question_audio(self, idx: int, text: str) -> np.ndarray:
        cache = OUT / f"q{idx:02d}_16k.pcm"
        if cache.exists():
            cached: np.ndarray = np.frombuffer(cache.read_bytes(), dtype=np.int16)
            return cached
        r = client().models.generate_content(
            model=cfg.SPIKE_TTS_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                    )
                ),
            ),
        )
        data = b""
        for cand in r.candidates or []:
            for part in (cand.content.parts if cand.content else None) or []:
                if part.inline_data and part.inline_data.data:
                    data += part.inline_data.data
        if not data:
            raise RuntimeError("TTS returned no audio")
        pcm16 = _lowpass_resample_24k_to_16k(np.frombuffer(data, dtype=np.int16))
        cache.write_bytes(pcm16.tobytes())
        _write_wav(OUT / f"q{idx:02d}.wav", pcm16.tobytes(), IN_RATE)
        return pcm16

    # --- one Live turn ----------------------------------------------------------------
    async def _run_turn(
        self,
        idx: int,
        item: dict[str, Any],
        audio: np.ndarray,
        behavior: str,
        scheduling: str,
        mode: str,
    ) -> TurnResult:
        res = TurnResult(idx=idx, question=item["q"], mode=mode)
        instruction = live_system_instruction(
            business_name=spike.SPIKE_BUSINESS,
            today_long=uz_format.format_date_long(spike.SPIKE_TODAY),
            context_lines=spike.context_lines(),
        )
        if self.variant == "answer":
            instruction = instruction.replace(
                "\n\nKontekst", f"\n{spike.ANSWER_RULE}\n\nKontekst", 1
            )
        conf = live_config(
            system_instruction=instruction,
            tool_specs=[spike.EVALUATE_PURCHASE_SPEC],
            behavior="non_blocking" if behavior == "non_blocking" else "blocking",
            silence_ms=self.silence_ms,
        )
        t_open = time.perf_counter()
        tok = await asyncio.to_thread(mint_token, conf)
        res.mint_ms = tok.mint_ms
        token_client = genai.Client(api_key=tok.token, http_options={"api_version": "v1beta"})
        t_conn = time.perf_counter()

        # frame index of the last voiced frame -> exact speech end inside the clip
        frames = [audio[i : i + FRAME_SAMPLES] for i in range(0, len(audio), FRAME_SAMPLES)]
        rms = [
            float(np.sqrt(np.mean(f.astype(np.float64) ** 2))) if len(f) else 0.0 for f in frames
        ]
        voiced = [i for i, v in enumerate(rms) if v > 500]
        last_voiced = voiced[-1] if voiced else len(frames) - 1

        out_audio = bytearray()
        heard: list[str] = []
        said: list[str] = []
        state: dict[str, Any] = {
            "speech_end": None,
            "first_audio": None,
            "tool_call": None,
            "tool_resp": None,
            "answer_audio": None,
            "done": False,
        }
        rng = np.random.default_rng(idx)

        async with token_client.aio.live.connect(
            model=tok.model,
            config=types.LiveConnectConfig(response_modalities=[types.Modality.AUDIO]),
        ) as session:
            t_ready = time.perf_counter()
            res.connect_ms = (t_ready - t_conn) * 1000
            res.session_ready_ms = (t_ready - t_open) * 1000

            async def sender() -> None:
                t0 = time.perf_counter()
                n = 0
                for i, f in enumerate(frames):
                    await session.send_realtime_input(
                        audio=types.Blob(data=f.tobytes(), mime_type=f"audio/pcm;rate={IN_RATE}")
                    )
                    if i == last_voiced:
                        state["speech_end"] = time.perf_counter()
                    n += 1
                    await asyncio.sleep(max(0.0, t0 + n * FRAME_MS / 1000 - time.perf_counter()))
                # open mic after the question: faint noise, real-time pace
                while not state["done"]:
                    noise = (rng.standard_normal(FRAME_SAMPLES) * 30).astype(np.int16)
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=noise.tobytes(), mime_type=f"audio/pcm;rate={IN_RATE}"
                        )
                    )
                    n += 1
                    await asyncio.sleep(max(0.0, t0 + n * FRAME_MS / 1000 - time.perf_counter()))

            async def receiver() -> None:
                deadline = time.perf_counter() + TURN_TIMEOUT_S
                answered_after_tool = False
                while not state["done"] and time.perf_counter() < deadline:
                    async for msg in session.receive():
                        now = time.perf_counter()
                        sc = msg.server_content
                        if sc:
                            if sc.interrupted:
                                res.interrupted += 1
                            for part in (sc.model_turn.parts if sc.model_turn else None) or []:
                                if part.inline_data and part.inline_data.data:
                                    if state["speech_end"] is None:
                                        res.cut_off = True
                                    if state["speech_end"] and state["first_audio"] is None:
                                        state["first_audio"] = now
                                    if state["tool_resp"] and state["answer_audio"] is None:
                                        state["answer_audio"] = now
                                        answered_after_tool = True
                                    out_audio.extend(part.inline_data.data)
                            if sc.input_transcription and sc.input_transcription.text:
                                heard.append(sc.input_transcription.text)
                            if sc.output_transcription and sc.output_transcription.text:
                                said.append(sc.output_transcription.text)
                            if sc.turn_complete:
                                no_tool_turn = state["tool_call"] is None and state["first_audio"]
                                if no_tool_turn or answered_after_tool:
                                    state["done"] = True
                        if msg.tool_call:
                            for call in msg.tool_call.function_calls or []:
                                if state["speech_end"] is None:
                                    res.cut_off = True
                                state["tool_call"] = state["tool_call"] or now
                                res.tool_called = True
                                res.tool_args = dict(call.args or {})
                                t0 = time.perf_counter()
                                try:
                                    payload = spike.evaluate_payload_for_model(
                                        call.args or {}, with_answer=self.variant == "answer"
                                    )
                                except ValueError as exc:
                                    payload = {"ok": False, "error": str(exc)}
                                res.tool_exec_ms = (time.perf_counter() - t0) * 1000
                                fr = types.FunctionResponse(
                                    id=call.id, name=call.name, response=payload
                                )
                                if behavior == "non_blocking":
                                    fr.scheduling = types.FunctionResponseScheduling(scheduling)
                                await session.send_tool_response(function_responses=[fr])
                                state["tool_resp"] = time.perf_counter()
                        if state["done"]:
                            break

            send_task = asyncio.create_task(sender())
            try:
                await receiver()
            finally:
                state["done"] = True
                await asyncio.gather(send_task, return_exceptions=True)

        await asyncio.to_thread(
            budget.record, "live", tok.model, seconds=max(1, round(time.perf_counter() - t_conn))
        )
        se = state["speech_end"]
        if se and state["first_audio"]:
            res.speech_end_to_first_audio_ms = (state["first_audio"] - se) * 1000
        if se and state["tool_call"]:
            res.speech_end_to_tool_call_ms = (state["tool_call"] - se) * 1000
        if state["tool_resp"] and state["answer_audio"]:
            res.tool_response_to_first_audio_ms = (
                state["answer_audio"] - state["tool_resp"]
            ) * 1000
        if se and (state["answer_audio"] or (state["first_audio"] and not state["tool_call"])):
            res.speech_end_to_answer_audio_ms = (
                (state["answer_audio"] or state["first_audio"]) - se
            ) * 1000
        res.heard = "".join(heard).strip()
        res.said = "".join(said).strip()
        res.audio_s = len(out_audio) / 2 / cfg.LIVE_OUTPUT_RATE
        low = (
            res.said.lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("ʼ", "'")
        )
        res.expect_hits = {e: e in low for e in item["expect"]}
        res.cyrillic_in_answer = any("Ѐ" <= ch <= "ӿ" for ch in res.said)
        res.ok = bool(state["first_audio"])
        _write_wav(OUT / f"a{idx:02d}_{mode}.wav", bytes(out_audio), cfg.LIVE_OUTPUT_RATE)
        return res

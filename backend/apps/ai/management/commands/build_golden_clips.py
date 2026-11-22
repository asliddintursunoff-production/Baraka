"""One-time: pre-record every demo answer (Q1–Q4 speech, side answers, fixed replies) with Gemini TTS.

Each clip is transcribed back and compared with its text (word similarity); a clip that does not
match well (mangled Uzbek, dropped or added words) is regenerated. Output:
frontend/public/golden/<key>.wav + apps/ai/data/golden/clips.json ({key: text}). Logs the real cost.

Usage: manage.py build_golden_clips [--only-missing]
"""

from __future__ import annotations

import difflib
import json
import re
import time
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from google.genai import types

from apps.ai import budget, demo
from apps.ai.golden_tools import _pinned
from apps.ai.views import _pcm_to_wav
from config import app_settings as cfg

OUT = demo.ROOT / "frontend" / "public" / "golden"
MANIFEST = Path(demo.__file__).parent / "data" / "golden" / "clips.json"
STYLE = (
    "Siz ona tili o'zbek bo'lgan tajribali diktorsiz. Quyidagi o'zbekcha (lotin yozuvidagi) matnni "
    "tabiiy, aniq va xotirjam ovozda, o'rtacha tezlikda o'qing. Har bir so'zni to'g'ri talaffuz "
    "qiling, hech narsa qo'shmang va hech narsani tashlab ketmang:\n\n"
)
MIN_SIMILARITY = 0.85


def texts() -> list[str]:
    out: list[str] = []
    for d in _pinned().values():
        out.append(" ".join(s["text"].strip() for s in d["speech_segments"] if s["text"]))
        if d.get("speech_short"):
            out.append(d["speech_short"].strip())
        for sd in d.get("side") or []:
            out.append(str(sd.get("say") or re.sub(r"\*\*", "", sd["answer"])).strip())
    out += [
        demo.OTHER_SAY,
        demo.GREET_SAY,
        demo.CHARTS_SAY,
        demo.EXPLAIN_SAY,
        demo.DECLINE_TEXT,
        demo.AMBIG_TEXT,
    ]
    return list(dict.fromkeys(t for t in out if t))


def tts(text: str) -> bytes:
    r = budget.generate_sync(
        "tts",
        model=cfg.TTS_MODEL,
        contents=STYLE + text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg.LIVE_VOICE_NAME)
                )
            ),
        ),
    )
    pcm = b"".join(
        p.inline_data.data
        for c in (r.candidates or [])
        for p in ((c.content.parts if c.content else None) or [])
        if p.inline_data and p.inline_data.data
    )
    if not pcm:
        raise RuntimeError("no audio")
    return _pcm_to_wav(pcm)


def heard(wav: bytes) -> str:
    r = budget.generate_sync(
        "stt",
        model=cfg.AI_MODELS["light"],
        contents=[
            types.Part.from_bytes(data=wav, mime_type="audio/wav"),
            "Bu audioni o'zbek tilida (lotin yozuvida) so'zma-so'z yozib ber. Faqat matnni qaytar.",
        ],
        config=types.GenerateContentConfig(
            max_output_tokens=2000,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel("LOW")),
        ),
    )
    return (r.text or "").strip()


def words(t: str) -> list[str]:
    return re.findall(r"[a-z']+", demo.normalize(t).replace("'", ""))


def similarity(a: str, b: str) -> float:
    # STT writes numbers as digits ("100 000"): compare both sides in spoken words
    return difflib.SequenceMatcher(None, words(demo.speakable(a)), words(demo.speakable(b))).ratio()


class Command(BaseCommand):
    help = "Pre-record the demo answers (TTS) and verify each clip by transcribing it back."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--only-missing", action="store_true")

    def handle(self, *args: Any, **opts: Any) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, str] = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        _, before = budget.spent()
        for text in texts():
            key = demo.speech_key(text)
            if opts["only_missing"] and key in manifest and (OUT / f"{key}.wav").exists():
                continue
            best: tuple[float, bytes, str] | None = None
            for attempt in range(2):
                t0 = time.perf_counter()
                spoken = demo.speakable(text)
                try:
                    wav = tts(spoken)
                    back = heard(wav)
                except Exception as exc:
                    self.stdout.write(f"  ! {key} attempt {attempt + 1}: {str(exc)[:120]}")
                    continue
                sim = similarity(spoken, back)
                secs = (len(wav) - 44) / 48000
                self.stdout.write(
                    f"  {key} try {attempt + 1}: {secs:.1f}s audio, similarity {sim:.2f}, "
                    f"{time.perf_counter() - t0:.1f}s"
                )
                if best is None or sim > best[0]:
                    best = (sim, wav, back)
                if sim >= MIN_SIMILARITY:
                    break
            if best is None:
                self.stdout.write(self.style.ERROR(f"FAILED {key}: {text[:60]}"))
                continue
            sim, wav, back = best
            (OUT / f"{key}.wav").write_bytes(wav)
            manifest[key] = text
            mark = "OK " if sim >= MIN_SIMILARITY else "LOW"
            self.stdout.write(f"{mark} {key} {sim:.2f} | {text[:70]}")
            if sim < MIN_SIMILARITY:
                self.stdout.write(f"     heard: {back[:200]}")
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
        _, after = budget.spent()
        self.stdout.write(f"clips: {len(manifest)}; cost of this run: ${after - before:.4f}")

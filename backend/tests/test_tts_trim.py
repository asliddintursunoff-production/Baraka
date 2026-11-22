"""TTS clips end with a loud ~0.2 s burst after the speech: it is cut (owner 2026-11-22)."""

import numpy as np

from apps.ai.views import trim_tail


def test_trailing_burst_removed_speech_kept():
    sr = 24000
    t = np.arange(sr) / sr
    speech = (8000 * np.sin(2 * np.pi * 220 * t)).astype(np.int16)
    silence = np.zeros(sr // 10, dtype=np.int16)
    burst = (
        (np.random.default_rng(0).normal(0, 12000, sr // 5)).clip(-32000, 32000).astype(np.int16)
    )
    out = np.frombuffer(trim_tail(np.concatenate([speech, silence, burst]).tobytes()), np.int16)
    assert len(out) >= len(speech) and len(out) <= len(speech) + len(silence)
    assert np.abs(out[-480:]).max() < 50  # ends quietly


def test_clean_clip_untouched_in_length():
    sr = 24000
    speech = (8000 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype(np.int16)
    out = np.frombuffer(trim_tail(speech.tobytes()), np.int16)
    assert len(out) == len(speech)

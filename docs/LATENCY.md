# LATENCY — measurements and gaps

All numbers are measured, not estimated. All voice numbers so far are from the **M0 voice spike** (2026-11-21, ~15:30–16:20 Tashkent, home network, `gemini-3.8-live`). Product-path measurements (`make latency`) start in M2/M3.

## How the voice spike measures
- **Python harness** (`manage.py voice_spike`):
  - 10 Uzbek questions are synthesized once with `gemini-3.8-flash-tts` and resampled to 16 kHz.
  - Each question opens a new session with a freshly minted ephemeral token.
  - The question is streamed as 20 ms PCM16 frames at real-time pace, followed by low-level noise (an open mic), so the server's own VAD decides when the user stopped.
  - **speech_end** = the moment the last voiced frame was sent. This includes the server's VAD silence wait (500 ms by default).
  - Raw results are in `backend/spike_out/results_*.json`; the model's audio is in `backend/spike_out/a*.wav`.
- **Browser path** (`/dev/voice`):
  - Headless Chrome with a fake microphone fed from the same WAVs, metrics read from the page.
  - Covers the real code path: parallel `getUserMedia` + token + AudioWorklets, then `ai.live.connect`, `toolCall` → `fetch('/api/dev/tools/…')` → card → `sendToolResponse`.
- Not measured yet: a real human on a real mic, barge-in with loudspeakers (echo cancellation), reconnect after `goAway`. These need you to test at `http://localhost:8000/dev/voice` (or :5173 with `make dev`).

## Results vs budget (spec §6)
Baseline = defaults: BLOCKING tools, VAD silence 500 ms, the model phrases the answer itself.

| Path | Budget p50 / p95 | Baseline (Python, run 1, n=10/5) | Browser (n=5) | Measured alternatives (**not enabled**) |
|---|---|---|---|---|
| `/live` open → session ready | ≤ 1.0 s / ≤ 1.5 s | **2.0 / 2.4 s** (mint 0.40 / 0.56, connect 1.59 / 1.93) | **2.06 s** p50 (1.88–2.93; token+mic+worklets 0.56–0.70, ws open 0.44–0.74, setup rest) | token prefetch removes the mint (P3) |
| speech end → first audio, no tool | ≤ 0.8 s / ≤ 1.5 s | **1.45 / 1.52 s** | 1.22, 1.44 s | VAD 300 ms: **1.18 / 1.29 s** (P2) |
| speech end → answer audio, one tool | ≤ 1.4 s / ≤ 2.0 s | **2.70 / 3.25 s** | 1.15–1.53 s from tool response to audio | ready-made `speech.answer`: **1.71 / 2.09 s** (P1) |
| `POST /api/tools/*` server time | ≤ 60 ms / ≤ 150 ms | — | 6–8 ms HTTP round trip (fake tool) | real engine in M3 |
| tool result → card painted | ≤ 100 ms | — | **1–14 ms** ✅ | — |

Breakdown of a tool turn (baseline): speech end → `toolCall` p50 1.08 s; tool execution ≈ 0; `sendToolResponse` → first audio p50 **1.57 s** / p95 2.16 s. The model's own generation after the tool result dominates, and it is server-side.

**Run 2 of the baseline** (16:05, n=10) overlapped a local Docker image build that was downloading packages. Token minting rose to 9–11 s on 4 questions (session ready p95 11.6 s). That run is kept in `spike_out/` but not used above. It still shows that token minting can spike, which is another reason to prefetch.

## WHEN_IDLE vs INTERRUPT (spec §5.6) — tool questions, n=5 each
| Mode | answer audio p50 / p95 | tool response → first audio p50 / p95 |
|---|---|---|
| **BLOCKING** | **2.70 / 3.25 s** | 1.57 / 2.16 s |
| NON_BLOCKING + WHEN_IDLE | 3.07 / 4.06 s | 1.81 / 2.44 s |
| NON_BLOCKING + INTERRUPT | 3.45 / 3.72 s | 2.08 / 2.44 s |

Our tools return in milliseconds, so NON_BLOCKING only adds scheduling overhead. **Default: BLOCKING** (set explicitly, because 3.8 Live defaults to NON_BLOCKING). If NON_BLOCKING is ever needed, INTERRUPT has the better p95.

## Quality — 10 Uzbek questions (baseline run 1, re-checked in every other run)
| # | Question (as spoken) | Heard right | Answered in Uzbek | Numbers read correctly | Notes |
|---|---|---|---|---|---|
| 1 | Hozir kassamda qancha pul bor? | ✅ | ✅ | ✅ 48,2 | added a generic advice sentence |
| 2 | Yigirma besh million so'mga yangi jihoz olsam…? | ✅ ("25 million") | ✅ | ✅ −6,2 · 10-dek · 12-yan | ❌ **content error**: said installments keep the safe limit (the tool says the opposite) |
| 3 | 25 millionga jihoz olsam, oylikka yetadimi? | ✅ | ✅ | ✅ 9,8 · 12-yan | skipped the main reason (−6,2 on 10-dek) |
| 4 | Slushay, … oborudovaniye olsam, zarplataga yetadimi? (Russian-mixed) | ✅ | ✅ | ✅ 12-yan | gave no amount |
| 5 | Eng qiyin kun qachon va qancha qoladi? | ✅ | ✅ | ✅ 10-dek · 18,8 | |
| 6 | Kredit to'lovi qachon va qancha? | ✅ | ✅ | ✅ 10-dek · 18,5 | |
| 7 | … uch oyga bo'lib to'lasam? Narxi yigirma besh million. | ✅ | ✅ | ✅ 9,8 · 12-yan | tool args `installments: 3` ✅ |
| 8 | Kassada qirq sakkiz million turibdi, normalno. O'n millionlik remont…? | ✅ ("normalno" dropped from the transcript, meaning kept) | ✅ | ✅ | tool args 10 000 000 ✅; the answer follows the fixed fake tool |
| 9 | O'tgan oy qancha foyda qildim? | ✅ | ✅ | — | ✅ "Bu ma'lumot jadvalingizda yo'q." |
| 10 | Ertaga ob-havo qanday bo'ladi? | ✅ | ✅ | — | ✅ polite refusal |

Totals across all saved runs (30 turns) plus run 1 (10) and the browser runs (5):
- Understanding **10/10**.
- Uzbek only **45/45** turns: 0 Cyrillic, no language switching, even for Russian-mixed questions.
- Numbers: **no invented or altered number**. Every spoken amount or date matched a `speech` string or the context, and none were read as digits.
- Tool arguments parsed correctly **every time**.

Weak spot: when the model phrases a tool answer itself, it picks facts inconsistently (Q2–Q4). In one case it inverted a fact (Q2). Variant P1 removes this: the model read the ready-made sentence verbatim 5/5 times.

## Proposals (measured, **not applied** — need your OK)
- **P1. Ready-made `speech.answer` in tool results** (built by `uz_format`, plus one extra system rule: "read speech.answer verbatim").
  - Tool turns: 2.70/3.25 s → **1.71/2.09 s**.
  - Fixes content selection: the answer is exactly the design text ("Yo'q, hozir olmang. Agar hozir olsangiz, o'ninchi dekabrda oylikka olti million ikki yuz ming so'm yetmay qoladi. Jihozni o'n ikkinchi yanvarda oling. Shunday reja tuzaymi?").
  - Cost: answers sound more templated; free phrasing remains for questions without a tool.
- **P2. VAD silence 500 → 300 ms.** No-tool first audio 1.45/1.52 s → **1.18/1.29 s**. Risk: it may cut off speakers who pause mid-sentence. Decide after you test with a real mic.
- **P3. Session pre-warm.**
  - (a) Prefetch the token when the Chat page loads or on hover of "Jonli gaplashish" (the spec already asks for hover). This removes 0.4–0.7 s, plus mint spikes up to 11 s. The new-session window is 60 s, so re-fetch when stale.
  - (b) Optionally also open the Live WebSocket on hover, so `/live` is ready on arrival. This is a step beyond the spec's prefetch.
  - Even with (a), connect + setup is ~1.2–1.6 s, so the ≤ 1.0 s budget is only reachable with (b).
- **P4.** The "Hozir hisoblayman" filler appeared in ~40 % of tool turns (first audio 0.82–1.1 s). With P1 the real answer is already fast. No action proposed.
- **Not proposed now:** switching the Live model (`gemini-3.1-flash-live-preview` is sync-only and older). It's measurable if P1–P3 are not enough.

## Chat model capacity (affects M3)
On 2026-11-21 `gemini-3.8-flash` answered every call with 503/504 (details in `AI_NOTES.md`). The chat budget (send → answer ≤ 2.5 s p50) cannot be met while that holds. A fallback chain will be proposed in M3.

## M4 — P2 silence test (thinking pauses), 2026-11-21
`manage.py voice_spike --pause-ms 600`: each of the 10 questions gets a 600 ms "thinking" pause inserted at the quietest word gap in the middle third of the sentence. Silence is set to 300 ms (`LIVE_SILENCE_DURATION_MS`). A turn counts as **cut off** if the model starts audio or calls a tool before the user's real speech end.

| Result | Value |
|---|---|
| Sessions | 10 (9 ok, 1 server `1006 abnormal closure`) |
| Cut off during the pause | **0 / 9** |
| speech end → first audio, p50 | 1 495 ms |
| speech end → answer audio after a tool, p50 | 3 800 ms |

The Live server's end-of-turn detection does not end the turn on a 600 ms mid-sentence pause, even at 300 ms silence. **Decision: 300 ms stays** (the rule was: raise it to 500 ms if more than 1 of 10 is cut off).

`make smoke-ai` (new key, paid tier) Live check: Q3 "25 millionga jihoz olsam, oylikka yetadimi?" → tool called, speech end → first audio 851 ms, answer audio after the tool 2 920 ms.

**Live limits (budget rules):** the page closes the session and releases the mic after 30 s with no speech in either direction, when the tab is hidden, when the user leaves the page, or after 5 min. Each token mint reserves 60 s of Live cost, and `/live/finish` replaces it with the real duration.

## M8 — `make latency` (final, 19:38)
| Page API (in-process, n=20) | p50 ms | p95 ms |
|---|---|---|
| `/api/dashboard` | 16 | 20 |
| `/api/forecast` | 9 | 12 |
| `/api/calendar` | 8 | 10 |
| `/api/knowledge` | 13 | 17 |
| `/api/sources` | 16 | 18 |
| `/api/alerts` | 8 | 10 |
| `/api/simulate` (25 mln preset, n=10, HTTP 200) | 10 | 12 |
| Recorded event (7 days) | n | p50 ms | p95 ms |
|---|---|---|---|
| chat · send_to_answer | 2 | 4563 | 6443 |
| chat · send_to_blocks | 2 | 28 | 32 |
| voice · interrupted | 1 | 0 | 0 |
| voice · session_ready | 9 | 2271 | 3027 |
| voice · speech_end_to_first_audio | 11 | 1443 | 3128 |
| voice · token_ready | 9 | 680 | 1864 |
| voice · tool_call_to_response | 5 | 10 | 22 |
| voice · tool_http | 5 | 6 | 8 |
| voice · tool_response_to_card | 5 | 2 | 14 |
| voice · tool_response_to_first_audio | 5 | 1521 | 2194 |
| voice · ws_open | 9 | 514 | 740 |

| AI usage (all time) | calls | in tok | out tok | sec | cost $ |
|---|---|---|---|---|---|
| live · gemini-3.8-live | 1 | 0 | 0 | 9 | 0.0038 |
| chat · gemini-3.5-flash-lite | 13 | 25323 | 1277 | 0 | 0.0030 |
| mapping · gemini-3.5-flash-lite | 4 | 6688 | 5173 | 0 | 0.0027 |
| check · gemini-3.8-flash | 2 | 58 | 14 | 0 | 0.0001 |
| check · gemini-3.5-flash-lite | 1 | 16 | 3 | 0 | 0.0000 |
| embedding · gemini-embedding-001 | 1 | 12 | 0 | 0 | 0.0000 |
| tts · gemini-3.8-flash-tts | 1 | 0 | 0 | 0 | 0.0000 |

**AI spend:** today $0.0096 / $0.50 · total $0.0096 / $4.00 (estimated from `AI_PRICES_PER_M_TOKENS`, profile `dev`)

Chat 'send → cards' p50 28 ms (budget 1.2 s). 'Send → answer' in the dev profile (3.5-flash-lite) is 2.8–4.6 s with the browser e2e. Voice speech end → first audio p50 1.4 s; after a tool, p50 1.5 s from tool response to audio. Page APIs are ≤ 20 ms p95 in-process.

# AI_NOTES — Gemini API facts we rely on

Checked 2026-11-21 against the official docs (the `ai.google.dev/gemini-api/docs/*` pages now redirect to `aistudio.google.com/docs/*`), the installed SDKs (`google-genai` 3.6.1 for Python, `@google/genai` 3.6.1 for JS), and real calls with the project key (`manage.py check_ai`, `manage.py voice_spike`).
"Verified" = we called it and it worked. "Docs" = documentation only.

## Models (`config/app_settings.py`)
| Role | ID | Status |
|---|---|---|
| chat | `gemini-3.8-flash` | listed. **On 2026-11-21 it returned 503 "high demand" / 504 on every call** (see "Capacity" below) |
| light | `gemini-3.5-flash-lite` | verified, ~0.5–0.9 s for a one-word reply |
| mapping | `gemini-3.8-flash` | same as chat |
| live | `gemini-3.8-live` | verified through an ephemeral token |
| embedding | `gemini-embedding-001` | verified: 768 dims; raw L2 norm ≈ 0.59, so we **normalize** before storing (docs: required for any size other than 3072). Shutdown 2028-05-14; successor `gemini-embedding-2` has an incompatible vector space |
| voice-spike TTS | `gemini-3.8-flash-tts` | used only to synthesize test questions |

`gemini-3.8-live-extended-thinking` exists but is not used (spec §4; it needs every tool to be NON_BLOCKING).

## Chat model (`gemini-3.8-flash`)
- Thinking: `thinking_config.thinking_level`. 3.8 Flash accepts `LOW | MEDIUM (default) | HIGH`. **`MINIMAL` is rejected**, so the lowest level is `LOW` (`CHAT_THINKING_LEVEL = "LOW"`). Don't send `temperature/top_p/top_k` (docs).
- Function calling plus structured output **in one request** is supported on Gemini 3.x (preview): `response_mime_type="application/json"` + `response_json_schema`. `check_ai` tests this; not yet verified because of the capacity problem.
- Retries: the SDK's default is 5 attempts with up to 60 s backoff. That's far too slow for our budget, so `apps/ai/gemini.py` sets `HttpRetryOptions(attempts=3, initial_delay=0.4, max_delay=2.0)` and a 30 s HTTP timeout.

### Capacity (observed 2026-11-21, ~15:00 Tashkent)
| model | result (LOW thinking, one-word prompt) |
|---|---|
| gemini-3.8-flash | 503 UNAVAILABLE "high demand" or 504 DEADLINE_EXCEEDED, every attempt |
| gemini-3.7-flash | 504 |
| gemini-3.6-flash | OK, 3.0–4.0 s |
| gemini-3.5-flash | OK, 3.2 s once, then 54 s |
Open decision for M3 (not changed without approval): a fallback chain for `chat`, e.g. `3.8-flash → 3.6-flash`, with a short per-attempt deadline.

## Live API (`gemini-3.8-live`)
### Ephemeral tokens (verified)
- `client.auth_tokens.create(config=CreateAuthTokenConfig(...))` on **`v1beta`**. The docs say v1beta; the SDKs still warn "v1alpha only", but v1beta works. Mint time is **0.4–0.6 s**.
- Fields: `uses=1`, `expire_time` (default +30 min), `new_session_expire_time` (default +60 s), `live_connect_constraints=LiveConnectConstraints(model, config)`, `lock_additional_fields`.
- `lock_additional_fields=[]` locks **exactly the fields we set**: model, modality, system instruction, tools, transcription, voice, VAD, compression. `session_resumption` is left unset, so the client can pass a resume handle. Omitting `lock_additional_fields` would lock the whole config.
- The token is `token.name` (`auth_tokens/…`). Browser: `new GoogleGenAI({apiKey: token, httpOptions: {apiVersion: "v1beta"}})`; the SDK then connects to `…GenerativeService.BidiGenerateContentConstrained?access_token=…`.
- Resuming a session does not count as a "use", so a reconnect with a handle can reuse the same token.

### Session config (what `apps/ai/live.py` sets)
- `response_modalities=[AUDIO]` (the only option on 3.8 Live).
- `input_audio_transcription` / `output_audio_transcription` = `AudioTranscriptionConfig(language_codes=["uz"])`. `uz` is in the Live list of 99 languages; the hint itself is undocumented for Uzbek, but it is accepted.
- **No language code for speech:** native audio picks the language itself, and `speechConfig.languageCode` does not include Uzbek. Uzbek-only output is enforced in the system instruction (rule 1).
- Voice: `speech_config.voice_config.prebuilt_voice_config.voice_name = "Kore"`.
- VAD: `realtime_input_config.automatic_activity_detection(silence_duration_ms=500, prefix_padding_ms=100)`. Docs recommend 500–800 ms; the server default is ~800 ms.
- `context_window_compression.sliding_window` lifts the 15-minute audio-session limit.
- **Must NOT be sent on 3.8 Live:**
  - `thinking_config`: not configurable; reasoning is built in.
  - `proactivity.proactive_audio=false`: proactive audio is always on, and sending false errors.
  - `enable_affective_dialog`: removed.

### Audio
- In: PCM16 LE mono, 16 kHz, `audio/pcm;rate=16000`, 20–40 ms chunks, sent via `sendRealtimeInput({audio})` (`mediaChunks` is deprecated).
- Out: PCM16 24 kHz in `serverContent.modelTurn.parts[].inlineData`. One event can carry several parts (audio + transcript).
- `sendRealtimeInput({audioStreamEnd: true})` when the mic pauses for more than 1 s.

### Tools
- Declarations are locked in the token: `tools=[{function_declarations:[{name, description, parameters_json_schema, behavior}]}]`.
- **On 3.8 Live the default behavior is `NON_BLOCKING`.** We set `behavior` explicitly on every declaration.
- `FunctionResponse.scheduling` (`SILENT | WHEN_IDLE | INTERRUPT`) applies only to NON_BLOCKING calls. We send it as a top-level `FunctionResponse` field, as typed in both SDKs (one docs page nests it inside `response`).
- `toolCallCancellation.ids[]` arrives when the user barges in during a call.

### Server messages and limits
- Message types: `setupComplete`, `serverContent{modelTurn, interrupted, turnComplete, generationComplete, inputTranscription, outputTranscription, waitingForInput}`, `toolCall`, `toolCallCancellation`, `goAway{timeLeft}`, `sessionResumptionUpdate{newHandle, resumable}`, `usageMetadata`.
- A connection lasts ~10 min (`goAway` arrives first). Resumption handles are valid for 2 h. Audio costs ~25 tokens/s.

## Voice-spike measurements
See `docs/LATENCY.md`.

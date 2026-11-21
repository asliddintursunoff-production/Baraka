# CLAUDE.md

AI CFO MVP for small Uzbek businesses (hackathon). The product name comes from the `APP_NAME` env var (default "BizPilot AI"); never hard-code it.

- Spec: `docs/BUILD_PROMPT.md` (re-read before every milestone).
- Plan, approved decisions (§6, which override earlier sections) and milestone log (§7): `docs/PLAN.md`.
- UI source of truth: `design/DESIGN.md` + `design/pages/*.html`. Copy values and Uzbek text exactly; the numbers in the files are only samples.
- Gemini API facts: `docs/AI_NOTES.md`. Latency results: `docs/LATENCY.md`.

## Commands
- `make up` / `make down`: whole app in Docker (db + web + scheduler); http://localhost:8000.
- `make install`: venv (`python3.12`, at `backend/.venv`) + pip + `npm ci`. System `python3` is 3.14; don't use it.
- `make db`: Postgres 16 + pgvector in Docker on **host port 5433** (5432 is a local Postgres 18).
- `make dev`: uvicorn --reload on :8000 + Vite on :5173 (open :5173; Vite proxies `/api` and `/app-config.js`).
- `make test`: pytest + ruff check/format + mypy (strict) + tsc + eslint + vitest. Must be green before a milestone commit.
- `make check-ai`: real API check of every model ID, embeddings, and a Live session via an ephemeral token.
- `make voice-spike`: 10 synthesized Uzbek questions against Live; output in `backend/spike_out/` (gitignored).
- Planned: `make seed` (`seed_demo --reset`, M2), `make latency` (`latency_report`, M8).

## Layout
- `backend/config/`: `settings.py` reads only the 8 env vars (`ENV_KEYS`). All other constants are in `app_settings.py`.
- `backend/apps/<app>/`: Django apps. `apps/engine` is pure Python; a test enforces no Django/network imports.
  Engine API (`apps.engine`): `forecast`, `simulate`, `evaluate_purchase`, `explain_day`, `spend_limit_until`, `aggregate_daily`, `inputs_hash`. Tiyin int64 inside, `Decimal` out. Golden fixtures: `backend/tests/engine/golden.py`.
- `backend/apps/ai/`: `gemini.py` (client with bounded retries, `scrub()`), `live.py` (Live config + token mint), `uz_format.py` (all Uzbek display/speech text), `prompts.py`, `spike.py` + `dev_views.py` (M0 spike, DEBUG only).
- `frontend/src/live/voiceClient.ts`: browser Live client (worklets in `frontend/public/worklets/`).

## Non-negotiables (from the spec)
- Numbers come only from `apps/engine`. The LLM never does arithmetic or invents amounts or dates.
- Money is `Decimal` / `NUMERIC(18,2)`, never `float` (the engine may use numpy int64 tiyin internally).
- Every business row is scoped by `business_id`. Tool args never contain `business_id`; it comes from the session.
- "Today" is the real Asia/Tashkent date from a single `today_for(business)`. The engine takes `today` as an argument. No frozen demo date.
- Secrets never go in logs, errors, the frontend bundle or git. Use `apps.ai.gemini.scrub()` on any error text.
- No Celery, Redis, Kafka, k8s, LangChain or separate vector DB. A library outside the approved list (PLAN §6.5) needs approval first.

## Git
- Local commit at the end of each milestone when tests are green ("M1: engine + golden tests"). Never add a remote or push without permission.

## Gemini gotchas (details in AI_NOTES)
- Tokens and Live use `v1beta`; ignore the SDK's "v1alpha only" warning.
- `gemini-3.8-flash` lowest thinking level is `LOW` (`MINIMAL` errors).
- `gemini-3.8-live`: no `thinking_config`, no `proactivity`, no affective dialog. Tools default to NON_BLOCKING, so set `behavior` explicitly.
- Uzbek output cannot be set by language code; it's enforced by the system instruction. Transcription hint is `language_codes=["uz"]`.

## Golden-model convention (verified)
`opening_balance` = **today's closing balance**; the forecast starts tomorrow; a purchase dated today is applied to today's close. Daily net trading = revenue × (1 − variable_cost_ratio).

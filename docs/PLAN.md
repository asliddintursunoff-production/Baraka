# PLAN — AI CFO MVP (`APP_NAME`, default "BizPilot AI")

Status: **approved 2026-11-21** with the decisions in §6. M0 in progress / see §7 for the per-milestone log.
Source of truth: `docs/BUILD_PROMPT.md` (spec), `design/DESIGN.md` + `design/pages/*.html` (UI).

---

## 0. Final mode (started 2026-11-21 19:15 +05, deadline 21:45; AI budget $5)
- The AI always answers in Uzbek only (Latin script): chat, voice and alerts.
- All pytest/vitest tests mock Gemini. Real calls only in `make check-ai` and `make smoke-ai` (≤ 5 chat calls + 1 Live session of ~20 s).
- `AI_PROFILE` in `app_settings`: `dev` → chat on gemini-3.5-flash-lite; `demo` → gemini-3.8-flash with the fallback chain. `DEBUG=false` means `demo`. No new env vars.
- Every LLM, Live and embedding call is logged in `AiUsage` (tokens or minutes + estimated cost). `AI_DAILY_BUDGET_USD = 0.50`, `AI_TOTAL_BUDGET_USD = 4.00`. Over the limit: chat → template answers (tool result + prepared text); Live disabled with "Bugungi ovoz limiti tugadi"; a warning is logged.
- Live: close the session and stop the mic after 30 s of silence, when the tab is hidden or the user leaves the page; one session is 5 min at most.
- Alerts and the 08:00 brief come from templates only; the scheduler never calls an LLM. Embeddings are cached by `text_hash`.
- Timebox: a task more than 10 min over is cut to its simplest working version; the rest goes to **Deferred** (§8). No refactoring, extra features, pixel polishing or broad tests. Critical tests only: golden, tenancy, normalization, OAuth, budget guard.
- Docker only for db; one image build at the very end. On Gemini errors, switch to the fallback immediately.
- Small decisions are logged as one line in §7; one-line report and a commit after each task.
- Cut order if late: M7 segment stats → M6 08:00 brief → M7 Knowledge page → M4 silence test. Never cut the demo path: login → dashboard (real banner) → Google connect + sheet → "25 mln jihoz olsam?" (chat + voice) → decision + cards → "Ha" → plan approved → correction → "Eslab qol" → forecast updated.

## 0. Pre-flight findings (already verified)

| Check | Result |
|---|---|
| Toolchain | Python 3.12.16 (`python3.12`), Node 22.22, npm 9.2, Docker 29 + Compose v5, GNU make. No `uv`/`pnpm` → plain `venv` + `npm`. |
| Ports | **5432 is taken by a local Postgres 18.** Docker `db` will be published on **5433**. 8000 and 5173 are free. |
| Gemini model IDs (§4) | `models.list` with the project key: `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.8-live` (bidi), `gemini-embedding-001` (embedContent): **all exist.** `gemini-3.8-live-extended-thinking` also exists (we won't use it, per §4). |
| `.env` | **Contains only one variable, named `GEMINI__API_TOKEN`** (double underscore, not `GEMINI_API_KEY`). `DJANGO_SECRET_KEY`, `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `APP_NAME`, `APP_URL`, `DEBUG` are missing. See Q1. |
| Git | The folder is **not a git repository**. See Q4. |
| Golden numbers (§5.3) | Prototyped the daily cash model in plain Decimal arithmetic. **All 8 expected results reproduce exactly** (table below). |

### Golden-model interpretation (this is what makes the numbers match)
- `opening_balance = 48.2 mln` is the **closing balance of today (2026-11-21)**: today's sales are already in it. The forecast series starts **tomorrow**.
- A purchase/expense dated **today** is applied to today's close (it is a new outflow, not yet in the 48.2).
- Daily net trading = `revenue(weekday) × (1 − 0.45)`; obligations hit on their exact date.
- Verdict and "lowest balance" use the point forecast (P50); P10/P90 is only the band and the confidence metric.

| Case | Computed | Expected |
|---|---|---|
| baseline | 18.815 on 2026-12-10 | 18,8 · 10-Dec · `yes` ✅ |
| buy 25 today | −6.185 on 2026-12-10 | −6,2 · `no` ✅ |
| buy on 2027-01-12 | 12.255 on 2027-01-12 | 12,3 · `yes` ✅ |
| 9 + 8 + 8 (21-Nov, 21-Dec, 21-Jan) | 9.815 on 2026-12-10 | 9,8 · `risky` ✅ |
| revenue −20 % | −7.504 on 2027-01-10 | −7,5 · `no` ✅ |
| +2 staff (6/month on the 10th) | 12.815 on 2026-12-10 | 12,8 · `yes` ✅ |
| `spend_limit_until(2026-12-10)` | floor₁ₘ(18.815 − 10) | 8 000 000 ✅ |
| `evaluate_purchase(25)` earliest `yes` date | **2027-01-12** (11-Jan gives 9.01 → `risky`) | 12-Jan ✅ |

The earliest-`yes` date is the same for 60- and 90-day horizons, and with recurring February obligations, so no deviation needs agreeing.
Cross-checks against the mockups also hold: 1-Dec close 48,9; 9-Dec close 78,9; 10-Dec "Savdodan kiradi +3,4" (= 6.2 × 0.55, net of variable costs); 15-Dec 30,8; 25-Dec 46,5; 10-Jan 30,8; 30-day obligations 108,5 (5 payments).

---

## 1. Key decisions (inside the spec, flagged so you can veto)

1. **Engine** (`apps/engine`, pure Python, no Django import, enforced by a test that imports it with Django absent from `sys.modules`). Internals use numpy `int64` **tiyin** arrays; every public output is `Decimal`. `simulate` = base arrays + delta vector → one `np.cumsum` → well under 5 ms.
2. **Installment alternative** = 3 monthly payments, rounded down to whole millions, remainder on the first payment → 25 → 9 + 8 + 8 (matches the design).
3. **`new_staff` cost is computed by the backend, never by the LLM:** `value` = number of people; monthly cost = `value × (payroll obligation ÷ staff_count)` on the payroll day (45 ÷ 15 × 2 = 6 mln). Needs a `Business.staff_count` field (seed: 15).
4. **Forecast cache:** per-process dict `business_id → (inputs_hash, EngineInput, ForecastResult)`. Validity check = one indexed `SELECT inputs_hash` from the latest `ForecastSnapshot` (works across several gunicorn workers without Redis). To make the cache-miss path a single SELECT too, `ForecastSnapshot` gets an extra **`inputs JSON`** column (compact engine input: 56 days of daily totals, obligations, rules, params; a few KB).
5. **API style:** DRF for validation/serializers and CRUD-ish endpoints; **native async Django views** for SSE chat and the hot `/api/tools/<name>` path (no DRF overhead there). Session auth + CSRF (`X-CSRFToken` header, also on `keepalive` fetches).
6. **Tenancy:** `TenantMiddleware` puts the session's business into a `contextvars.ContextVar` (asgiref propagates it into `sync_to_async` threads). `TenantScopedManager` raises `TenantContextMissing` without it; `unscoped` manager for scheduler/migrations; scheduler wraps each business in `with tenant_context(b):`.
7. **`APP_NAME` to the frontend:** prod: Django renders the built `index.html` with an inline `window.__APP_CONFIG__` and a server-side `<title>`. Dev: Vite proxies `/api` **and** `/app-config.js` to Django, so the same code path works on :5173.
8. **Tailwind v3.4** (the spec says "tokens into `tailwind.config`"; v4 has no config file). shadcn/ui components are copied into `src/components/ui` (that's how shadcn works), themed with the DESIGN.md tokens only.
9. **Fonts self-hosted:** Inter + Space Grotesk woff2 (OFL) committed under `frontend/public/fonts/`, with `<link rel="preload">`, no Google Fonts request at runtime.
10. **Calendar/Day breakdown** shows "Savdodan kiradi" as **net** trading inflow (revenue − variable costs), exactly like `Calendar.html` (78,9 + 3,4 − 63,5 = 18,8).
11. **Seed history** (8 months) is generated so the last 8 weeks average **exactly** 5.8…8.2 per weekday (zero-sum noise per weekday), the last-30-day KPIs reproduce `Main.html` (kirgan 196,4 · chiqqan 178,0 · "18,4 mln ortib qoldi" · ▼ 3,3 % vs October), and the cash account is back-solved so today's close is exactly 48,2. Weekday residuals are non-zero, so the P10/P90 band is real.
12. **Live tool declarations** come from the same registry as chat (`apps/ai/tools.py` → Gemini `FunctionDeclaration` JSON). They are locked into the ephemeral token's `liveConnectConstraints` if the API allows it; otherwise the frontend passes them, fetched from the backend (verify in M0 spike → `docs/AI_NOTES.md`).

---

## 2. Milestones

Each milestone ends with: tests green (`pytest`, `ruff`, `mypy`, `tsc --noEmit`, `eslint`), a short "done / left" note appended here, and a stop for your OK.

### M0 — Skeleton (+ Live/Uzbek spike, see Q7)
- `backend/` Django 5 project per §5.1 with all apps registered (empty models), `config/app_settings.py` (all constants: `AI_MODELS`, `EMBEDDING_DIM`, `SYNC_INTERVAL_MIN=15`, `DEFAULT_SAFE_MIN`, horizons, `DAILY_BRIEF_AT="08:00"`, `NIGHTLY_AT="03:00"`).
- `settings.py` reads **only** the 8 env vars; `DATABASE_URL` parsed with `urllib.parse` (no extra lib); psycopg 3 pool (`OPTIONS={"pool": True}`); Fernet key via HKDF(`DJANGO_SECRET_KEY`).
- Migration enabling `CREATE EXTENSION IF NOT EXISTS vector`.
- `/api/health` → `{"ok": true, "app": APP_NAME}`; SPA catch-all view; `Server-Timing` middleware stub.
- `frontend/` Vite + React 18 + TS + Tailwind 3 + shadcn base + Router + TanStack Query; shows `APP_NAME`.
- `docker-compose.yml` (db only, `pgvector/pgvector:pg16`, host port 5433), `Makefile` (`db dev test seed latency`), `.env.example` (exactly 8 keys), `.gitignore`, `README.md` stub.
- `manage.py check_ai`: `models.list` → every ID present; tiny `generateContent` on chat/light; `embedContent` returns 768 dims; create an ephemeral token; open a Live session with the token, send a text turn, receive audio. Fails with a clear message.
- **Spike:** generate an Uzbek question with `gemini-3.8-flash-tts`, stream it into `gemini-3.8-live`, measure the time to first audio and check the Uzbek transcription and the tool call. Findings → `docs/AI_NOTES.md`.
- Docs check of the Live config, ephemeral tokens (`auth_tokens.create`, v1alpha), `Behavior.NON_BLOCKING`, `FunctionResponse.scheduling`, transcription config, thinking-level param name → `docs/AI_NOTES.md`.

### M1 — Engine
- `apps/engine/{types.py, forecast.py, rules.py, simulate.py, purchase.py, explain.py, uncertainty.py}`.
- Tests: all 8 golden cases (§0 table), rule application per type, `insufficient_data` (< 2 weeks, no segment), segment blend weight `1 − min(1, weeks/8)`, P10/P90 monotonic widening, **benchmark `simulate` < 5 ms** (median of 200 runs), "engine does not import Django".
- `apps/ai/uz_format.py` + tests: `format_mln`, `uz_number_words`, `uz_ordinal_date`, locative ("10-dekabrda"), month names, values 0, 1, 15, 100, 1 000, 2 500 000, 6 200 000, 18 800 000, 63 500 000, negatives.

### M2 — Data + tenancy + dashboard
- All §5.2 models + migrations + indexes (`(business, txn_date)`, `(business, due_date)`, `(business, -created_at)` on snapshots; HNSW cosine on `MemoryItem.embedding`).
- `seed_demo` (Navro'z Kafe + 5 synthetic Tashkent cafés, users, rules, accuracy, AI-noticed card, memory items; works without OAuth).
- `GET /api/dashboard` (whole Main page in one call), `/api/forecast?horizon=`, `/api/calendar?month=`, `POST /api/simulate`.
- Pages: Main, Forecast (simulator with 3 presets; free text goes through the chat orchestrator with only `simulate_change`/`evaluate_purchase` enabled), Calendar (month grid + DayDetail). AppSidebar with business switcher. `/login`.
- Tests: tenant isolation per app, `django_assert_max_num_queries` on dashboard/forecast/calendar, API snapshot of the seeded numbers vs the mockups.

### M3 — Tools + chat
- `apps/ai/tools.py` registry (9 tools, uniform ≤ 2 KB envelope: `ok, verdict, facts, display, speech, ui_blocks, proposed_plan, insufficient_data`). Backend builds the `ui_blocks`.
- `POST /api/tools/<name>`: arg validation, cache → snapshot, no LLM / embeddings / network, `Server-Timing`, `AuditLog`.
- `POST /api/chat/messages` SSE: parallel memory search + cash status → chat model (lowest thinking) ≤ 3 tool rounds → `blocks` event as soon as a tool returns → structured final answer → **number guard** (regex-extract numbers/dates, normalize, must match tool `facts`/`display`; one retry; then template text) → `answer`, `done`. Persists `Message` + `AuditLog`.
- Chip fast path (no LLM, ≤ 300 ms). `ActionPlan` propose/approve (`POST /api/actions/<id>/approve`, idempotent), `/api/reminders`.
- Chat page: proactive 08:00 message, AnswerCard (Verdict, CompareBars, ActionSteps, "Ha, shunday qilamiz" → `approved`, "Boshqa yo'l bormi?", "Tinglash", collapsible "Qanday hisobladim?"), right "Nimaga asoslandim" panel, composer with chips/mic/live button.
- Tests: guard accepts/rejects, orchestrator with a fake Gemini client, idempotent confirm, chip latency.

### M4 — Live voice
- `POST /api/live/session` (ephemeral token, uses = 1, ≤ 1 500-token preloaded context, no retrieval), `POST /api/live/finish` (save transcript + blocks; summary by `light` model in a background asyncio task → `MemoryItem`).
- Live page: parallel mic + token + AudioWorklet load on open; prefetch on hover of "Jonli gaplashish"; 16 kHz PCM16 20–40 ms frames; 24 kHz ring-buffer playback starting on the first chunk; barge-in buffer flush on `interrupted`; tool call → `/api/tools/<name>` (keepalive) → render cards → `sendToolResponse`; captions (spoken words white); auto-reconnect; "Yozib so'rash" fallback; LiveOrb respects `prefers-reduced-motion`.
- Measure `WHEN_IDLE` vs `INTERRUPT` scheduling (p95) → default + `docs/LATENCY.md`. Frontend telemetry → `POST /api/telemetry`.

### M5 — Google Sheets
- OAuth (scopes `openid email …/spreadsheets.readonly`), encrypted refresh token, link paste, `spreadsheets.get`, header-row detection, 20-row sample → `mapping` model (structured output), confidence < 0.8 → "Tasdiqlang", `SheetMapping` confirmation (Connect page), opening-balance question.
- Normalizers (amounts, dates incl. Sheets serials and Cyrillic months, direction, names) with fixture-driven tests (`backend/fixtures/sheets/`, `FakeSheetsClient`); `DataIssue` instead of guessing.
- Sync: advisory lock, `values.batchGet`, `row_hash` diff, re-mapping on header-signature change, backoff, then engine → snapshot → `insights.evaluate` → cache invalidation. Sources page.

### M6 — Proactivity
- Deterministic alert rules (§5.8), `dedupe_key`, auto-close; alert text by `light` model with only `display` values, template fallback; daily brief 08:00 Asia/Tashkent; banner + "Nima qilish kerak" + bell; `GET /api/alerts?since=` polled on focus and every 60 s.

### M7 — Learning
- Correction → `RuleCandidate` (light model, structured) → "To'g'ri, eslab qol" → `BusinessRule` + `MemoryItem(rule)`, duplicate check (cosine ≥ 0.9), forecast recomputed + cache invalidated.
- Nightly: pattern detection (≥ 3 times, ±3 days, ±15 %), accuracy (MAPE) + EWMA weekday factors (α = 0.3), segment stats (only `n ≥ 5`, no names/amounts) + `segment_insight` memory. Knowledge page. All vector searches filtered by `business_id = current OR business_id IS NULL` (tested).

### M8 — Speed + deploy
- `manage.py latency_report` / `make latency` (p50/p95 by channel and event); fix or document every over-budget path in `docs/LATENCY.md`.
- Multi-stage Dockerfile (node build → python runtime, WhiteNoise), Railway `web` + `scheduler` (same image, `python manage.py run_scheduler`) + Postgres with pgvector; README (local run, Google OAuth setup in Testing mode, deploy).
- Rehearse the 3-minute demo script end to end.

---

## 3. Libraries outside §2 — need your approval (§10)

| Library | Why |
|---|---|
| `gunicorn`, `uvicorn` | Named in §2 as the ASGI server; listed here only for completeness. |
| `whitenoise` | Named in §2 (static files). |
| `psycopg[binary,pool]` | psycopg 3 + its pool package (`psycopg_pool`). |
| `ruff`, `mypy`, `django-stubs`, `djangorestframework-stubs` (dev) | §10 requires ruff + mypy; mypy on Django is not usable without the stubs. |
| `pytest-asyncio` (dev) | Testing the async orchestrator / SSE / Live token code. |
| Frontend: `class-variance-authority`, `clsx`, `tailwind-merge`, `tailwindcss-animate`, `@radix-ui/*` (only the primitives we use: switch, collapsible, dialog, dropdown) | These are shadcn/ui's own runtime dependencies. |
| Frontend dev: `eslint`, `typescript-eslint`, `eslint-plugin-react-hooks`, `autoprefixer`, `postcss` | §10 tooling, Tailwind build. |
| Frontend dev: `vitest` (optional) | Unit tests for the PCM resampler / ring buffer and `UiBlockRenderer`. Can drop if you prefer. |

Not added: `dj-database-url` (parsed by hand), `django-cors-headers` (same domain), `django-vite` (small hand-written view), `@fontsource/*` (fonts committed as files), `celery`/`redis`/`langchain` (banned).

---

## 4. Risks

1. **Uzbek in Gemini Live (biggest risk).** Uzbek ASR/TTS quality, and whether the model reads `speech` strings verbatim, are unknown until measured. *Mitigation:* the M0 spike; captions + an output-transcript number check logged per turn; the "Yozib so'rash" fallback.
2. **Live API surface churn.** Ephemeral-token constraints, `NON_BLOCKING`, `scheduling` and transcription flags may differ on `gemini-3.8-live`. *Mitigation:* verify against ai.google.dev first and record in `AI_NOTES.md`; keep a fallback where the client passes the tool config.
3. **Chat latency budget (≤ 2.5 s p50 to full answer)** with tool-call + structured-answer round trips. *Mitigation:* lowest thinking level, ≤ 3 rounds, blocks streamed before text, chip fast path. Check early whether tools + `response_schema` can share one call on 3.8-flash.
4. **Railway + pgvector.** Railway's default Postgres may lack the `vector` extension. *Mitigation:* use Railway's pgvector template/image; verify in M8, and earlier if you give access.
5. **Arbitrary sheet layouts.** Mapping quality depends on the LLM. *Mitigation:* confidence threshold UI, a `DataIssue` for anything ambiguous, fixtures for messy sheets.
6. **Demo-date drift.** All mockup numbers assume today = 2026-11-21. That is today, but a rerun tomorrow shifts every number (see Q2).
7. **Scope vs time.** 9 milestones is a lot. The demo-critical path is M0 → M1 → M2 → M3 → M4. M5–M7 can be thinner if time runs short (seed covers their UI).

---

## 5. Open questions (my recommendation first)

**Q1. `.env` contents.** It has only `GEMINI__API_TOKEN`; the spec's last line says `GEMINI_API_KEY` and OAuth keys are there, but they aren't.
→ *Recommend:* you rename it to `GEMINI_API_KEY`, or allow me to. I add `APP_NAME`, `APP_URL=http://localhost:8000`, `DEBUG=true`, a generated `DJANGO_SECRET_KEY`, and a local `DATABASE_URL` (port 5433). You add `GOOGLE_OAUTH_CLIENT_ID/SECRET` before M5. Until then Sheets runs on `FakeSheetsClient` + `seed_demo`.

**Q2. Frozen demo date.** The demo must show 18,8 / 10-dekabr every time it is run, and the mockups assume 2026-11-21.
→ *Recommend:* a constant `DEMO_TODAY = date(2026, 11, 21)` in `app_settings.py`, honoured only for businesses with a new `Business.is_demo=True` flag (set by `seed_demo`). Real businesses always use the real Tashkent date.

**Q3. Seeded rules conflict with the golden numbers.**
- `Chat.html` says "Siz o'rgatgan **2** ta qoida", and its demo *teaches* the Agro Go'sht +15 days rule. `Knowledge.html` already shows that rule as the 3rd one. So Knowledge is the state *after* the demo.
- The "Bayram oldidan juma–shanba savdosi yuqori" `weekday_factor` rule ("Dekabr prognoziga qo'shildi"), if active in Dec–Jan, changes the January numbers. E.g. ×1.1 on the last two Fri/Sat pairs of December would make revenue −20 % → −6,1 instead of −7,5, and moves the recommended purchase date to **11-Jan instead of 12-Jan**.
→ *Recommend:* seed **2** rules (oylik-on-the-10th priority, plus the holiday rule) and let the demo create the 3rd. Give the holiday rule a period outside the 90-day window (before Navro'z, March 2027), so it has no numeric effect on the demo screens. The Main "AI yangiliklari" card then says "Mart prognoziga qo'shildi". Similarly, the segment "January dip" only enters through the segment prior, whose weight is 0 with 8 months of history. Alternative: keep the December wording and accept that the January numbers differ from the mockups.

**Q4. Git.** → *Recommend:* `git init` in M0 with `.env` ignored, and one commit per finished milestone, only when you say so.

**Q5. Libraries in §3.** → Approve all, or strike any.

**Q6. Railway deploy (M8).** → *Recommend:* I prepare the Dockerfile, Railway config and README steps, and you run the deploy from your account, unless you want to give me Railway CLI access.

**Q7. Live spike in M0.** → *Recommend:* yes, half a day in M0 to measure Uzbek Live quality and latency before building pages around it.

**Q8. Stop after every milestone?** The spec says to stop after each one. → *Recommend:* keep that for M0–M1, where engine numbers and Live findings need your eyes, then allow M2–M3 to run back to back if the tests stay green.

---

## 6. Decisions from review (2026-11-21) — these override the recommendations above

1. **`.env`**: key renamed to `GEMINI_API_KEY`; local values filled in (DB on port 5433); OAuth ID/secret left empty until M5 (user adds them). The key is never printed, logged or committed.
2. **No frozen date.** "Today" is always the real Asia/Tashkent date from a single `today_for(business)`; no `demo_today`/`is_demo` field. The engine takes `today` as an argument; golden tests pass `date(2026, 11, 21)`.
   `seed_demo` builds data **relative to today**: 8 months of history, recurring obligations on the real calendar (10th salary + loan, 1st rent, 15th tax, 25th supplier). The opening cash is solved so that the lowest balance in the next 60 days is **18–20 mln**, and "buy 25 mln" is `no` on any day with a later safe date recommended.
   `seed_demo --reset` works on any day. `seed_demo --export demo_navroz.xlsx` writes the same data as a realistic messy spreadsheet (several sheets, Uzbek headers, mixed date formats). The user uploads it to Google Sheets and connects it in M5; from then on the demo business runs live from that sheet only.
   `POST /api/sources/sync` ("Hozir yangilash") syncs immediately and returns the result. No number or date is hard-coded in the frontend.
3. **Seed rules**: golden tests run on clean input without rules, plus a separate test per rule type. `seed_demo` enables 2 rules: "oylik har oy 10-sanada, kechiktirib bo'lmaydi", and a holiday rule tied to a real holiday period (Navro'z, March). The Agro Go'sht +15 rule is **not** seeded; the demo creates it through chat.
4. **Git**: initialized. After each milestone with green tests, a local commit (e.g. "M1: engine + golden tests"). No remote and no push without permission.
5. **Libraries approved**: shadcn/ui deps (Radix, cva, clsx, tailwind-merge, tailwindcss-animate); lint/type tools (ruff, mypy, django-stubs, drf-stubs, eslint, typescript-eslint, prettier); test tools (pytest, pytest-django, pytest-asyncio, vitest). Any other category → ask first.
6. **Railway**: we prepare everything (Dockerfile, web/scheduler start commands, healthcheck, migration step, step-by-step README covering env vars per service, pgvector, OAuth redirect URI); the user deploys.
7. **Voice spike in M0**: `/dev/voice` (ephemeral token → gemini-3.8-live → mic → Uzbek answer, one fake `evaluate_purchase` with a fixed answer and uz_format speech fields). Measure session ready, speech_end → first_audio (with and without tool), and the tool round trip. Test 10 real Uzbek questions (numeric, Russian-mixed). Results → `docs/LATENCY.md`. If quality is bad, propose fallbacks; don't change anything without agreement.
8. **Stops**: after M0, after M1; M2 + M3 back to back if green; stop after M4 (user tests voice); stop before M5 (OAuth keys); M6 + M7 back to back; stop after M8. Each stop gets a short report: done, tests, latency, next risks.
9. **Docker** (user request during M0: "dockerda ko'tar"): `docker compose up` runs the whole app (db + web + scheduler from the same image); `make dev` stays for hot-reload development.

## 7. Milestone log

### M0 — Skeleton + voice spike (done 2026-11-21)
**Acceptance**
- ✅ `make db` + `make dev` (uvicorn :8000 + Vite :5173; Vite proxies `/api` and `/app-config.js`) and `make up` (db + web + scheduler in Docker; web healthy).
- ✅ `/api/health` → `{"ok": true, "app": APP_NAME}` (`?deep=1` also checks the DB; used as the healthcheck).
- ✅ React is served by Django (WhiteNoise, hashed assets immutable). `APP_NAME` is injected into `<title>` and `window.__APP_CONFIG__`.
- ✅ pgvector 0.8.7 enabled by migration. ✅ `.env.example` has exactly the 8 keys (tested).
- ⚠️ `check_ai`: all 5 model IDs exist. The light model, embeddings (768 dims) and Live via ephemeral token all pass. **`gemini-3.8-flash` generate failed with 503/504 "high demand" all afternoon** (provider capacity, see AI_NOTES), so tools + JSON in one call is not verified yet.
- ✅ Voice spike: `/dev/voice` + `manage.py voice_spike`. Results in `docs/LATENCY.md`.

**Also done:** `uz_format` (moved up from M1) with 55 tests; `Server-Timing` middleware (db/engine/llm/total); `POST /api/telemetry` → `LatencyEvent`; `run_scheduler` skeleton; Dockerfile (node build → python runtime, non-root) + `docker/start-web.sh`; pinned requirements; README stub; `docs/AI_NOTES.md`.

**Tests:** 82 pytest + ruff + ruff format + mypy strict; tsc + eslint + vitest (2).

**Changes vs plan:** Live tokens use `v1beta` (not v1alpha). Chat thinking level is `LOW` (`MINIMAL` is rejected). Tool behavior default is BLOCKING (measured best). There is one bounded retry policy instead of the SDK's 5×/60 s.

**Open for the user (from M0):**
1. LATENCY.md P1–P3 (answer template, VAD 300 ms, pre-warm): measured, not applied.
2. Chat model fallback chain if `gemini-3.8-flash` capacity stays bad (decide before M3).
3. `seed_demo --export demo_navroz.xlsx` needs an xlsx writer: `openpyxl` (pandas' engine). It's a new library category, so it needs approval before M2.

### M1 — Financial Engine (done 2026-11-21)
**Acceptance**
- ✅ All spec §5.3 golden tests pass on clean input without rules, for both 60- and 90-day horizons:

  | Case | Result |
  |---|---|
  | baseline | 18,8 · 10-Dec · yes |
  | buy 25 today | −6,2 · 10-Dec · no |
  | buy on 12-Jan | 12,3 · 12-Jan · yes |
  | 9 + 8 + 8 | 9,8 · risky |
  | revenue −20 % | −7,5 · 10-Jan · no |
  | +2 staff | 12,8 · 10-Dec · yes |
  | `spend_limit_until(10-Dec)` | 8 000 000 |
  | `evaluate_purchase(25)` | no → recommended 12-Jan |

  The mockup cross-checks also pass (25-Nov 40,4 · 1-Dec 48,9 · 9-Dec 78,9 · 15-Dec 30,8 · 25-Dec 46,5 · 10-Jan 30,8; 10-Dec breakdown 78,9 + 3,4 − 63,5; 30-day payments 108,5 / 5).
- ✅ A separate test group per rule type: payment_shift, recurring, weekday_factor (absolute + yearly Navro'z, neutral in winter), priority, ignore (payments and history).
- ✅ `simulate` benchmark: p50 ≈ 0.02 ms, p95 < 0.07 ms (budget 5 ms). `forecast(90)` p50 0.36 ms; `evaluate_purchase` p50 0.13 ms.
- ✅ `uz_format` tests (done in M0). ✅ The engine does not import Django (AST + subprocess test).

**Files:** `apps/engine/{types,money,dates,rules,history,forecast,scenario,purchase,explain,serialize}.py`; tests in `backend/tests/engine/`. Total: 147 pytest, ruff, mypy strict.

**Engine decisions (veto if you disagree)**
1. `no` only when the balance is negative **on a day with a critical payment**. A negative balance on a day with only deferrable payments → `risky`.
2. Unpaid payments dated today or earlier hit today's close.
3. `spend_limit_until` uses the lowest balance from today to the end of the forecast, not just up to `until`, because a purchase lowers every later balance.
4. `evaluate_purchase` always looks 90 days ahead and only proposes dates with ≥ 35 days of forecast after them, so the next payroll day stays visible.
5. The segment prior carries only the weekday **shape** (no amounts, per §5.9). So zero own history is `insufficient_data` even with a segment.
6. Days without rows inside the observed history span count as zero sales.
7. Confidence = min(history score: 8+ weeks high / 4+ medium; margin score: distance of the lowest day from the threshold in spreads, ≥ 1.28 high / ≥ 0.5 medium).
8. Fields added beyond spec §5.3:
   - `ObligationIn.category`: payroll is needed to price `new_staff`; also used by M6 alerts.
   - `EngineInput.staff_count`.
   - `PreparedObligation.date_fixed`: rules never move a payment whose date came explicitly from the sheet.
   - `serialize.py`: canonical input JSON + `inputs_hash`, for `ForecastSnapshot.inputs/inputs_hash`.

### M2 — Data + tenancy + dashboard (done 2026-11-21)
- All §5.2 models + migrations (HNSW cosine index); `TenantScopedManager` raises without a context; isolation tests per app; tampered sessions are ignored.
- `seed_demo [--reset] [--export x.xlsx]`, data relative to today. Navro'z variable cost is **42 %** (45 % fails "safe date exists" on 22/186 days, mainly in February).
- 62-day tests in two windows (Nov–Jan and Jan–Mar): lowest 18–20 mln, buy 25 → no, a safe date exists.
- Engine changes:
  - a purchase must be covered on its own day (shortage there → `no`);
  - `deferrals` advice for `risky`;
  - `spend_limit_until(purchase_date=)`;
  - salary = last payroll ÷ staff_count;
  - `StaffCountUnknown` → ask the user;
  - purchase search horizon 120 days.
- Pages: Main, Forecast (3 presets + free text, parsed deterministically), Calendar (+ add payment, reminder). Each is one API call.
- Warm latency: dashboard p50 9.9 ms (≤ 10 queries), forecast 4.7 ms, calendar 3.9 ms. Snapshot cache: hit = 1 SELECT, miss = 2.
- Visual check: `scripts/visual_check.py` (Playwright + system Chrome) at 1440 / 390 px, no page overflow.
- Decisions:
  - tailwind-merge is configured with the design tokens;
  - segment news shows its real usage ("Maslahatlarda hisobga olinadi"), not the mockup's "Prognozga hisobga olindi";
  - openpyxl and playwright are dev-only dependencies.

### M3 — Tools + chat (done 2026-11-21)
- **Tools:** registry of 10 tools (spec 9 + `set_staff_count`), one set for chat and Live. Every tool returns `say` (P1) and an answer template. `/api/tools/<name>` takes p50 < 60 ms (tested).
- **`confirm_plan`:** the backend itself requires an explicit "ha" in the user utterance; it does not trust the LLM.
- **Plans:** `evaluate_purchase` creates the PROPOSED plan itself, saving one LLM round.
- **Chat SSE:**
  - chips use no LLM;
  - purchase-looking text runs a speculative `evaluate_purchase` (blocks in ~40 ms);
  - fallback chain 3.8-flash → 3.6-flash → 3.5-flash-lite with a 5 s deadline and circuit breaker;
  - number guard + one retry, then the engine template;
  - control tools (remember_fact, …) always use the template wording.
- **Learning:** correction → deterministic parser (LLM fallback) → candidate with an engine-made example and warning → "To'g'ri, eslab qol" → rule → forecast refreshed.
- **Chat page:** built by a subagent against `docs/API_CHAT.md`. Browser e2e: cards 43 ms, answer 6.9 s on the free tier (Gemini 3.8-flash quota 20/day exhausted), approve and learn both work.
- **Decisions:**
  - the SDK timeout is 10 s (server minimum) while our 5 s deadline uses `asyncio.wait_for`;
  - the psycopg pool is off in tests;
  - the approved purchase plan's "execution" is an in-app reminder.
- **Open:** chat send → answer is 2.5 s p50 only on a paid tier; on the free tier, 3.8-flash 429 + 3.6-flash timeout cost ~5 s before flash-lite answers.

### M5 — Google Sheets via Drive Picker (done 2026-11-21)
- **Done:**
  - OAuth (`openid email drive.file`, PKCE, single-use session state, Fernet-encrypted refresh token per business, `invalid_grant` → `reauth_required`);
  - Picker config (short-lived access token only);
  - `SourceReader` (Google Sheets / Drive .xlsx / fake);
  - header detection + heuristics + one LLM mapping call (confidence < 0.8 → confirm);
  - row-hash diff ingestion with DataIssues;
  - confirm and "Hozir yangilash" streamed as SSE;
  - 15-min scheduler sync with modifiedTime skip, advisory locks and backoff;
  - Connect and Sources pages.
- **Tests:** OAuth mocked (state CSRF, single-use, open redirect, denial), picker-config never exposes the refresh token, invalid_grant, demo export reproduces the seed forecast (low point within 100k so'm), modifiedTime skip, add/delete row diff, issue resolution, tenant isolation, xlsx dates/numbers.
- **Decisions (one line each):**
  - openpyxl is a runtime dependency (Drive .xlsx reading), not dev-only;
  - new sheet kind `cash_balance`: the opening cash comes from a "Kassa" sheet, else one onboarding question;
  - 9th env var `GOOGLE_PICKER_API_KEY` (the Picker needs a browser API key);
  - a planned payment found in two sheets (e.g. Chiqim "Muddat" and the NBU kredit schedule) counts once: same due date, amount and category;
  - payroll and loan sheets regenerate their future obligations on every sync (the sheet is the truth);
  - first confirm replaces the seeded demo data (`replace_seed_data`), and later syncs are diffs;
  - the demo export's Kassa row is **yesterday's** end-of-day balance, so today's rows (and any row the owner adds) roll forward and move the forecast;
  - sync log entries carry a `tone` (success/muted/error) for colour.
- **Verified live:** the OAuth start URL is accepted by Google (no redirect_uri_mismatch). The Picker and the real Sheets read are the user's manual acceptance test.

## 8. Deferred
- 19:22 Budget guard: `AiUsage` logs every chat/light/mapping/TTS/STT/Live/check call with an estimated cost (prices in `app_settings`, estimates). Live mint reserves 60 s and `/live/finish` sets the real seconds. `make check-ai` and `make smoke-ai` pass with the new key (smoke $0.0021).
- Decision: embeddings are not called at runtime in the MVP (memory uses recency), so there is no `text_hash` cache yet; one is added if M7 embeds.
- Decision: P2 silence test (10 Q, 600 ms mid-sentence pause, silence 300 ms, free tier before the key change): 0/9 cut off, 1 session error → 300 ms stays.
- 19:30 M5 finished: browser e2e (DEBUG FakeReader `POST /api/dev/sources/demo`) map → confirm → dashboard 6.5 s, the sheet reproduces the seed forecast exactly, an added expense row + "Hozir yangilash" → cash 44,3 → 41,3 mln.
- Decision: the loan sheet's payment column is the "Jami" header, never "Qoldiq" (the LLM mapping marked all four money columns as amount → 34,7 mln remaining debt was counted as a payment).
- Decision: the Sources page shows files whenever files exist (even if the Google credential is gone).
- Decision: scheduled syncs re-map new/changed sheets with heuristics only (no LLM); `seed_demo --export` without `--reset` only exports.
- Decision: during work, Django runs on host :8000 (uvicorn --reload) + local `run_scheduler`; Docker runs only db.
- Sources page: per-sheet "Yangi · +N" and row counts for non-transaction sheets (they show the file-level state / 0).

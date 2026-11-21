# BizPilot AI (`APP_NAME`)

AI CFO for small businesses in Uzbekistan. It reads Google Sheets, forecasts daily cash, warns about risky days, and answers "can I afford it?" by text and live Uzbek voice.
The product name comes from the `APP_NAME` env var.

Spec: `docs/BUILD_PROMPT.md` · Plan and status: `docs/PLAN.md` · Gemini notes: `docs/AI_NOTES.md` · Latency: `docs/LATENCY.md`

## Requirements
- Docker with Compose v2
- For local development without Docker: Python 3.12, Node 22, GNU make

## Configuration
Copy `.env.example` to `.env` and fill it in. These 9 variables are the only ones the app reads:

| Variable | Meaning |
|---|---|
| `APP_NAME` | product name shown everywhere (default `BizPilot AI`) |
| `APP_URL` | public base URL: OAuth redirect, `ALLOWED_HOSTS`, CSRF |
| `DEBUG` | `true` locally, `false` in production |
| `DJANGO_SECRET_KEY` | long random string; also the source of the token-encryption key (HKDF) |
| `DATABASE_URL` | `postgres://user:pass@host:port/db` |
| `GEMINI_API_KEY` | Gemini API key (backend only, never sent to the browser) |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth web client (Drive Picker + Sheets) |
| `GOOGLE_PICKER_API_KEY` | API key for the Google Picker (browser) |

## Run everything in Docker
```bash
make up        # db + web + scheduler; open http://localhost:8000
make down
```
`web` runs migrations on start, then serves the API and the built React app on :8000.

## Local development (hot reload)
```bash
make install   # venv (python3.12) + pip + npm ci
make db        # Postgres 16 + pgvector on host port 5433
make dev       # Django (uvicorn --reload) on :8000 + Vite on :5173 — open http://localhost:5173
make test      # pytest + ruff + mypy + tsc + eslint + vitest
make check-ai  # verifies every Gemini model ID, embeddings and a Live session with your key
```

## Voice spike (M0)
- `http://localhost:5173/dev/voice` (DEBUG only) opens a Live session with an ephemeral token. Speak Uzbek. There is one fake tool, `evaluate_purchase`, with a fixed answer.
- `make voice-spike` runs 10 synthesized Uzbek questions against the Live model. Results and audio go to `backend/spike_out/`.

## Google Cloud setup (Sheets via Drive Picker)
The app asks for only `openid`, `email` and `https://www.googleapis.com/auth/drive.file`. With `drive.file` it can open **only the files the user picks** in the Google Picker, and it can read both native Google Sheets and `.xlsx` files on Drive. These are non-sensitive scopes, so no Google security review is needed.

1. **Project:** create one at <https://console.cloud.google.com> and note its project **number**: the digits at the start of the OAuth client ID, also used as the Picker `appId`.
2. **APIs** (APIs & Services → Library): enable **Google Drive API**, **Google Sheets API** and **Google Picker API**.
3. **Google Auth Platform → Branding:** app name (same as `APP_NAME`), support email, logo (optional). Add the app domain later, when going public.
4. **Audience:** User type **External**, publishing status **Testing**. Add every tester's Gmail under **Test users**. Until verification, users see "Google hasn't verified this app": click *Continue*.
5. **Data access (scopes):** add `openid`, `.../auth/userinfo.email` and `.../auth/drive.file`. Nothing else.
6. **Clients → Create client → Web application.**
   - Authorized JavaScript origins: `http://localhost:8000`, `http://localhost:5173` (dev) and `https://<your-railway-domain>`.
   - Authorized redirect URIs: `http://localhost:8000/api/integrations/google/callback` and `https://<your-railway-domain>/api/integrations/google/callback`. The redirect is always `APP_URL` + `/api/integrations/google/callback`, so `APP_URL` must match exactly.
   - Put the client ID and secret into `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`.
7. **Credentials → Create API key** for the Picker → `GOOGLE_PICKER_API_KEY`.
   - Restrict it to the **Google Picker API**.
   - Add HTTP referrers `http://localhost:8000/*`, `http://localhost:5173/*` and `https://<your-railway-domain>/*`.
8. **Use it:** log in → `/onboarding/connect` → "Google bilan ulash" → pick the spreadsheet(s) → check the columns → "Tasdiqlash va tahlilni boshlash".

Demo file: `make seed` then `backend/.venv/bin/python backend/manage.py seed_demo --reset --export demo_navroz.xlsx`. Upload `demo_navroz.xlsx` to Drive. You can leave it as `.xlsx` or open it with Google Sheets ("Save as Google Sheets"); both work. Then pick it in the Picker.

**Going public later** (leaving Testing mode):
- a verified domain;
- a public home page and a privacy policy URL on that domain (Branding page);
- the app's terms of service (optional);
- "Publish app" on the Audience page.

`drive.file` is not a sensitive scope, so verification is a brand review only (days, not weeks). While in Testing, refresh tokens expire after 7 days; the app then shows "Qayta ulash".

## AI budget
- Every Gemini call (chat, mapping, TTS/STT, Live, embeddings) is logged in `AiUsage` with an estimated cost. Prices are estimates in `backend/config/app_settings.py`.
- Limits: `AI_DAILY_BUDGET_USD = 0.50`, `AI_TOTAL_BUDGET_USD = 4.00`. When a limit is reached, chat answers from templates (engine numbers + prepared text) and voice shows "Bugungi ovoz limiti tugadi".
- `DEBUG=true` (dev profile): chat uses only `gemini-3.5-flash-lite`. `DEBUG=false` (demo profile): `gemini-3.8-flash` → `3.6-flash` → `3.5-flash-lite`.
- Tests never call Gemini. The only paid commands are `make check-ai` and `make smoke-ai` (5 chat turns + 1 Live session, about $0.01).
- `make latency` prints page/voice/chat p50/p95 and the AI spend table.

## Deploy (Railway)
The repo has one image (`Dockerfile`: React build + Django) and two services: **web** and **scheduler**.

1. **New project → Deploy from GitHub repo** (push the repo to GitHub first).
2. **Database:** add PostgreSQL with pgvector. Use the *pgvector* template (`pgvector/pgvector:pg16`); the first migration runs `CREATE EXTENSION vector`.
3. **web service** (from the repo):
   - Settings → Config-as-code: `railway.json` (Dockerfile build, start `/app/docker/start-web.sh`, health check `/api/health`).
   - `start-web.sh` runs `migrate` and then gunicorn + uvicorn workers on `$PORT`.
   - Settings → Networking → **Generate domain**, e.g. `bizpilot.up.railway.app`.
4. **scheduler service:** add the same repo again as a second service, with Config-as-code `railway.scheduler.json` (start `python manage.py run_scheduler`, no HTTP health check). It runs the 15-minute sync and the 08:00 brief. It never calls an LLM.
5. **Variables** (both services; use Railway's *Shared variables*):

   | Variable | web | scheduler | Value |
   |---|---|---|---|
   | `APP_NAME` | ✓ | ✓ | `BizPilot AI` |
   | `APP_URL` | ✓ | ✓ | `https://<your-domain>` (exact, no trailing slash) |
   | `DEBUG` | ✓ | ✓ | `false` |
   | `DJANGO_SECRET_KEY` | ✓ | ✓ | the same long random string in both (it also derives the token-encryption key) |
   | `DATABASE_URL` | ✓ | ✓ | `${{Postgres.DATABASE_URL}}` (reference to the DB service) |
   | `GEMINI_API_KEY` | ✓ | – | Gemini key (billing enabled) |
   | `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | ✓ | ✓ | the OAuth web client |
   | `GOOGLE_PICKER_API_KEY` | ✓ | – | Picker API key |

6. **Google Cloud:** add `https://<your-domain>` to the OAuth client's *Authorized JavaScript origins*. Add `https://<your-domain>/api/integrations/google/callback` to *Authorized redirect URIs*. Add `https://<your-domain>/*` to the Picker API key's HTTP referrers.
7. **Demo data (once):** in the web service shell, `python manage.py seed_demo --reset`. Log in with `demo@demo.uz` / `demo12345`.
8. **Check:** `https://<your-domain>/api/health?deep=1` returns `{"ok": true, ...}`.

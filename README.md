# BizPilot AI (`APP_NAME`)

AI CFO for small businesses in Uzbekistan. It reads Google Sheets, forecasts daily cash, warns about risky days, and answers "can I afford it?" by text and live Uzbek voice.
The product name comes from the `APP_NAME` env var.

Spec: `docs/BUILD_PROMPT.md` · Plan and status: `docs/PLAN.md` · Gemini notes: `docs/AI_NOTES.md` · Latency: `docs/LATENCY.md`

## Requirements
- Docker with Compose v2
- For local development without Docker: Python 3.12, Node 22, GNU make

## Configuration
Copy `.env.example` to `.env` and fill it in. These 8 variables are the only ones the app reads:

| Variable | Meaning |
|---|---|
| `APP_NAME` | product name shown everywhere (default `BizPilot AI`) |
| `APP_URL` | public base URL: OAuth redirect, `ALLOWED_HOSTS`, CSRF |
| `DEBUG` | `true` locally, `false` in production |
| `DJANGO_SECRET_KEY` | long random string; also the source of the token-encryption key (HKDF) |
| `DATABASE_URL` | `postgres://user:pass@host:port/db` |
| `GEMINI_API_KEY` | Gemini API key (backend only, never sent to the browser) |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client for Sheets (needed from M5) |

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

## Deploy (Railway)
Step-by-step instructions are added in M8.

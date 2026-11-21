# BizPilot AI — developer commands. Python 3.12 venv in backend/.venv, Node in frontend/.
SHELL := /bin/bash
PY := $(CURDIR)/backend/.venv/bin/python
MANAGE := cd backend && $(PY) manage.py

.PHONY: install db up down dev migrate test test-backend test-frontend lint seed latency check-ai smoke-ai voice-spike build

install:            ## create venv + install backend and frontend deps
	test -x $(PY) || python3.12 -m venv backend/.venv
	$(PY) -m pip install -q -r backend/requirements-dev.txt
	npm --prefix frontend ci --no-audit --no-fund

db:                 ## Postgres 16 + pgvector in Docker (host port 5433)
	docker compose up -d --wait db

up:                 ## whole app in Docker: db + web (API + built React) + scheduler
	docker compose up -d --build --wait db web
	docker compose up -d scheduler
	@echo "-> http://localhost:8000"

down:
	docker compose down

migrate: db
	$(MANAGE) migrate --noinput

dev: migrate        ## Django (ASGI, autoreload) on :8000 + Vite on :5173 (open :5173)
	@trap 'kill 0' EXIT; \
	(cd backend && $(PY) -m uvicorn config.asgi:application --reload --port 8000 --log-level warning) & \
	npm --prefix frontend run dev & \
	wait

test: test-backend test-frontend   ## all tests + linters + type checks

test-backend:
	cd backend && $(PY) -m pytest
	cd backend && $(PY) -m ruff check .
	cd backend && $(PY) -m ruff format --check .
	cd backend && $(PY) -m mypy .

test-frontend:
	npm --prefix frontend run typecheck
	npm --prefix frontend run lint
	npm --prefix frontend test

seed:               ## demo data (M2)
	$(MANAGE) seed_demo --reset

latency:            ## p50/p95 per channel/event (M8)
	$(MANAGE) latency_report

check-ai:           ## verify every Gemini model ID + Live/embedding with the real key
	$(MANAGE) check_ai

smoke-ai:           ## the only paid smoke test: 5 chat calls + 1 Live session (~20 s)
	cd backend && $(PY) manage.py smoke_ai

voice-spike:        ## automated Uzbek Live test (10 questions); results in backend/spike_out/
	$(MANAGE) voice_spike --behavior blocking

build:
	npm --prefix frontend run build

#!/bin/sh
# Web process: Django ASGI app (API + built React) behind gunicorn/uvicorn workers.
# Migrations run on every start (docker compose and Railway); RUN_MIGRATIONS=0 skips them.
set -e
cd /app/backend
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi
# Optional demo data (demo@demo.uz): only when none exists yet, so redeploys keep it.
if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo --if-empty || echo "seed_demo skipped (see the error above)"
fi
exec gunicorn config.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 --graceful-timeout 20 --keep-alive 75 \
  --access-logfile -

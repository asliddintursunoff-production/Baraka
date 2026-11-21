#!/bin/sh
# Web process: Django ASGI app (API + built React) behind gunicorn/uvicorn workers.
# Migrations run here for docker compose; on Railway they run as the pre-deploy command.
set -e
cd /app/backend
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi
exec gunicorn config.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 --graceful-timeout 20 --keep-alive 75 \
  --access-logfile -

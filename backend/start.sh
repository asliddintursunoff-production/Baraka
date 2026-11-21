#!/bin/sh
# Web process: migrate, optional demo data, then the Django ASGI app on $PORT.
set -e
python manage.py migrate --noinput
if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo --if-empty || echo "seed_demo skipped (see the error above)"
fi
exec gunicorn config.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 --graceful-timeout 20 --keep-alive 75 \
  --access-logfile -

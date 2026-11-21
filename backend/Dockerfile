# syntax=docker/dockerfile:1
# Backend only (Django API). Railway: Root Directory = backend. The frontend is on Vercel.
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY requirements.txt ./
RUN pip install --retries 10 --timeout 120 -r requirements.txt
COPY . ./
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    && chmod +x start.sh \
    && useradd --create-home --uid 10001 app && chown -R app /app
USER app
EXPOSE 8000
# migrate (+ optional demo seed) then gunicorn/uvicorn on $PORT.
# The scheduler service uses the same image with the start command: python manage.py run_scheduler
CMD ["./start.sh"]

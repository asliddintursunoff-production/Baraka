# syntax=docker/dockerfile:1
# Stage 1: build the React app
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime (Django API + static React build via WhiteNoise)
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --retries 10 --timeout 120 -r requirements.txt
COPY backend/ ./
COPY docker/ /app/docker/
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN DJANGO_SECRET_KEY=collectstatic-only python manage.py collectstatic --noinput \
    && useradd --create-home --uid 10001 app && chown -R app /app
USER app
EXPOSE 8000
CMD ["/app/docker/start-web.sh"]

# syntax=docker/dockerfile:1
# Frontend service (Railway, Root Directory = frontend): React build served by Caddy.
# /api/* and /app-config.js are proxied to the backend service (BACKEND_URL), so the
# browser talks to one domain: cookies, CSRF and Google OAuth work without CORS.
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . ./
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /app/frontend/dist /srv
ENV PORT=8080
EXPOSE 8080

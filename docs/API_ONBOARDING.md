# Onboarding + "no data, no answer" API (contract)

All JSON. Session auth (cookie) + CSRF header `X-CSRFToken` like the rest of the app (`src/lib/api.ts`).

## GET /api/me  (also returned by login, register, onboarding/business, demo/start, me/business)
```json
{
  "user": {"email": "...", "first_name": "...", "last_name": ""},
  "business": {"id": 7, "name": "Navro'z Kafe", "city": "Toshkent", "is_demo": false} | null,
  "businesses": [{"id": 7, "name": "...", "city": "...", "role": "owner", "is_demo": false}],
  "onboarding_step": "business" | "connect" | "review" | "analyzing" | "done",
  "data_status": "no_data" | "short_history" | "ok",
  "history_days": 9
}
```
- `onboarding_step`: `business` = profile not filled; `connect` = no source picked; `review` = picked, columns not confirmed; `analyzing` = confirmed, first sync not finished; `done`. A demo business is always `done` + `ok`.
- Anonymous: 403 (as today).

## POST /api/auth/register
Body `{"first_name": "Abdusamad", "email": "a@b.uz", "password": "min 8 chars", "accept_terms": true}` → 201 + me payload (logged in; an EMPTY business is created, no seed data; `onboarding_step = "business"`).
Errors 400 `{"error": "email_taken" | "weak_password" | "terms_required" | "invalid", "message": "<Uzbek text>"}`.

## POST /api/onboarding/business
Body `{"name": "Navro'z Kafe", "kind": "cafe"|"shop"|"pharmacy"|"other", "city": "Toshkent", "staff_count": 15, "salary_day": 10, "safe_min": "10 000 000" (optional, string)}` → me payload (`onboarding_step` becomes `connect`). Errors 400 `{"error": "invalid", "message": "..."}`.

## POST /api/demo/start
No body. Creates (first time, ~2 s) or reuses the user's own **separate** demo business ("Demo kafe", `is_demo: true`, seeded) and switches the session to it → me payload. The real business stays gated.

## POST /api/me/business  `{"business_id": 7}` → me payload (existing switcher).

## 409 no_data
While the current business has no confirmed + synced source, these return `409 {"code": "no_data", "message": "Avval jadvallaringizni ulang."}`:
`/api/dashboard`, `/api/forecast`, `/api/calendar`, `/api/simulate`, `/api/chat/*`, `/api/tools/*`, `/api/live/session` (GET + POST). No Live token is issued.

## First sync (FirstSync page)
The column-review confirm is unchanged: `POST /api/sources/confirm` (SSE: `progress {text, pct}`, `done {...}`, `error {message}`) — it saves the mapping AND runs the first sync. During onboarding the Connect page hands this same request body to `/onboarding/analyzing` (router state) and FirstSync performs it and shows the progress. If FirstSync is opened without that state (reload), it calls `POST /api/sources/sync` (SSE, same events). After `done`: `GET /api/dashboard` → `banner` {headline, reason, instruction} is "AI'NING BIRINCHI XULOSASI".

## Pricing
`window.__APP_CONFIG__.pricing` (from `app_settings.PRICING`):
`{"trial": {"price_uzs": 0, "days": null, "sheets": null, "chat_per_day": null, "voice_minutes": null}, "business": {"price_uzs_month": null}}`. `null` → render the design placeholder (`[N]`, `[narx]`) verbatim. Never invent numbers.

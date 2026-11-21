# Design addendum: public pages, onboarding and the "no data" rule

Same rules as `DESIGN.md` (tokens, components, Uzbek copy kept verbatim, no hard-coded numbers).
`BizPilot AI` in the files is a placeholder: render `APP_NAME` everywhere.

## New screens

| File | Route | Who sees it |
|---|---|---|
| `Landing.html` | `/` | Anonymous visitors. Logged-in users are redirected (see "Routing") |
| `Pricing.html` | `/pricing` | Everyone. Prices are `[narx]` / `[N]` placeholders: render them from a `PRICING` constant in `app_settings`; do not invent numbers |
| `Login.html` | `/login` | Anonymous |
| `Register.html` | `/register` | Anonymous. On success → `/onboarding/business` |
| `Onboarding.html` | `/onboarding/business` | Step 1: business name, type, city, staff count, salary day, safe minimum (optional) |
| `Connect.html` (existing) | `/onboarding/connect` | Steps 2–3: Google connect, Picker, column review. Its stepper must show the 4 steps below |
| `FirstSync.html` | `/onboarding/analyzing` | Step 4: live progress of the first sync (SSE), then the first AI insight and "Bosh sahifaga o'tish" |
| `Gate.html` | shown inside the app shell | Tweak `state=nodata`: nothing connected yet. `state=short`: under 14 days of history |

Onboarding stepper everywhere: **1 Biznes · 2 Jadval ulash · 3 Ustunlarni tasdiqlash · 4 Birinchi tahlil**.

The dashboard moves from `/` to **`/dashboard`**. Other app routes are unchanged: `/chat`, `/live`, `/forecast`, `/calendar`, `/knowledge`, `/sources`.

## Routing (frontend guard + backend authority)

`GET /api/me` returns `onboarding_step` (`business | connect | review | analyzing | done`) and
`data_status` (`no_data | short_history | ok`).

- Anonymous on an app route → `/login`.
- Logged in on `/`, `/login`, `/register` → the current onboarding step, or `/dashboard` when `done`.
- `onboarding_step != done` → every app route redirects to the current step.
- `data_status = no_data` (all sources disconnected later) → app shell shows `Gate` (`nodata`); only "Ma'lumotlar" stays clickable.
- `data_status = short_history` → app works, but forecast, simulator and purchase decisions show `Gate` (`short`) content in place of numbers.

## The "no data, no answer" rule (hard requirement)

The AI never answers from data it does not have.

- Backend is the authority: dashboard, forecast, calendar, simulate, chat, tools and live-session endpoints return
  `409 {"code": "no_data"}` while the business has no confirmed, synced source. Live tokens are not issued.
- `short_history`: forecast-type tools return `insufficient_data=true` and no verdict; chat may answer only about
  current cash and upcoming payments, and says plainly that a forecast needs at least 2 weeks of data.
- A real business never sees seed or demo numbers. "Demo kafe bilan sinab ko'rish" switches the user into a
  **separate** demo business (seeded, labelled "Demo" in the sidebar switcher). The real business stays gated.
- Registration creates an empty business. No seed data is written into it.

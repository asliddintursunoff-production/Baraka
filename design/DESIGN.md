# BizPilot AI — Design handoff

This folder is the **source of truth for the frontend look**. Rebuild these screens in
React + TypeScript + Tailwind + shadcn/ui + Recharts so they match visually.

## How to read the files in `pages/`

Each `pages/*.html` file is one screen exported from a design canvas.

- Markup and **inline `style="…"` values are exact**: colors, sizes, spacing, radii and copy.
  Copy them into Tailwind classes or theme tokens. Do not invent new values.
- `<x-dc>`, `<helmet>`, `<script src="./support.js">` and the
  `<script type="text/x-dc">` block are canvas runtime. **Ignore the runtime itself**, but read
  the class's `state` and `renderVals()`: they describe the interactive behaviour you must
  reproduce (selected scenario, selected calendar day, live voice playback).
- `<sc-for list="{{ items }}" as="x">` means "map over items"; `<sc-if value="{{ flag }}">`
  means "render only when flag is true". `{{ path }}` is a value from `renderVals()`.
- **All numbers in the files are synthetic demo data** from one consistent cash model
  (see "Demo data" below). In the app they come from the backend. Never hard-code them
  in components.
- **UI copy is Uzbek (Latin script) and must be kept as written**, including the apostrophe
  in words like `to'lov`, `so'm`, `o'g'ir`.

## Screens

| File | Route | What it is |
|---|---|---|
| `Main.html` | `/` | Dashboard: advice banner, 4 KPI cards, 60-day forecast chart, "Nima qilish kerak" steps, AI news, obligations table, revenue/expense bars, floating "AI bilan gaplashish" button |
| `Chat.html` | `/chat` | AI CFO chat: proactive AI message, user voice message, **AI answer card** (verdict, compare bars, numbered steps, approve buttons, listen button, collapsible "Qanday hisobladim?"), learning example, composer with chips + mic + live button, right "Nimaga asoslandim" panel |
| `Live.html` | `/live` | Full-screen dark live voice mode: animated orb, live captions with spoken words highlighted, cards that appear on the right while AI speaks, voice approval, controls |
| `Forecast.html` | `/forecast` | Forecast chart + "Agar shunday qilsam-chi?" simulator (3 presets + free text) with a verdict card, "Muhim kunlar" grid |
| `Calendar.html` | `/calendar` | Month grid with payments per day and end-of-day balance, clickable day, right day-detail panel with AI advice |
| `Knowledge.html` | `/knowledge` | "AI bilimi": accuracy-over-weeks bars, "AI sezdi — to'g'rimi?" confirm card, business rules with on/off, shared segment insights |
| `Sources.html` | `/sources` | Data sources: sync status, connected sheets table, issues, sync log |
| `Connect.html` | `/onboarding/connect` | One-time Google Sheets connect wizard: stepper, files, AI column mapping table, rows to fix, auto-sync toggle |

The sidebar is identical on every app screen (`Main`, `Chat`, `Forecast`, `Calendar`,
`Knowledge`, `Sources`). Build it once as `<AppSidebar active=… />`. `Live` and `Connect`
have no sidebar.

## Design tokens

### Typography
- Body: **Inter** 400/500/600/700. Headings and big numbers: **Space Grotesk** 600/700.
- Sizes used: 12, 13, 14, 15, 16, 17, 20, 22, 24, 26, 30, 32 px. Body text in chat = 16 px.
- Uppercase micro-labels: 12–13 px, weight 700, letter-spacing 0.04em.

### Colors
| Token | Hex | Use |
|---|---|---|
| `bg` | `#F5F6F8` | page background |
| `surface` | `#FFFFFF` | cards |
| `surface-muted` | `#F9FAFB` / `#FCFCFD` | inner panels |
| `border` | `#E4E7EC` | card borders |
| `border-subtle` | `#EAECF0` | table rows, dividers |
| `border-input` | `#D0D5DD` | inputs, secondary buttons |
| `ink` | `#101828` | primary text, dark banner, AI avatar |
| `text-2` | `#344054` | body secondary |
| `text-3` | `#475467` | muted |
| `text-4` | `#5D6679` | hints (still ≥ 4.5:1 on white) |
| `primary` | `#1D4ED8` | primary buttons, links, user bubbles, forecast line |
| `primary-hover` | `#1E3A8A` | |
| `primary-soft` | `#EFF4FF` | active nav, selected items |
| `primary-border` | `#84ADFF` | dashed/selected outlines |
| `success` / `success-bg` | `#067647` / `#ECFDF3` | "Yetadi", "Pul yetadi" |
| `warning` / `warning-bg` / `warning-accent` | `#B54708` / `#FFFAEB` / `#F79009` | "Ehtiyot", hard day |
| `danger` / `danger-bg` / `danger-strong` | `#B42318` / `#FEF3F2` / `#D92D20` | "Yetmaydi", shortage zone, end call |
| Live mode: `live-bg` / `live-surface` / `live-border` | `#0B1220` / `#101A2E` / `#1D2939` | dark live screen |

Status is never color-only: every colored state also has a word ("Yetadi", "Yetmaydi",
"Ehtiyot") or an icon.

### Shape and spacing
- Card radius 16 px; inner cards 12 px; buttons 10–12 px; pills/chips 999 px.
- Page padding 28 px × 36 px; gaps between sections 20–24 px; inside cards 14–22 px.
- **Every clickable target is at least 44 px tall.**
- Layout: sidebar `flex: 1 1 240px` + content `flex: 999 1 560px` in a wrapping row, so the
  sidebar stacks on top on phones. Tables sit in `overflow-x: auto`.
- Icons: simple 2 px stroke line icons (use `lucide-react`; match shapes in the files).

## Components to build (and where they appear)

- `AppSidebar` — all app screens.
- `AdviceBanner` (dark `ink` card: label, one-line decision, one instruction, 2 buttons) — Main.
- `KpiCard` — Main.
- `ForecastChart` (Recharts): blue line, light-blue uncertainty band, red "Pul yetmaydigan
  zona" below 0, dashed amber "Xavfsiz chegara" line, callout for the hardest day, optional
  dashed scenario overlay — Main, Forecast.
- `ActionSteps` (numbered 1-2-3, colored by severity, date label + one sentence) — Main, Chat, Live.
- `CompareBars` (diverging horizontal bars around a zero line, value + "Yetadi/Yetmaydi") — Chat, Live.
- `AnswerCard` = Verdict header + one-sentence reason + `CompareBars` + `ActionSteps` +
  approve buttons + listen button + collapsible details — Chat.
- `ScenarioSimulator` (radio-like preset buttons, free text input, verdict card) — Forecast.
- `MonthCalendar` + `DayDetail` — Calendar.
- `RuleRow` (title, source line, on/off) and `ConfirmCard` — Knowledge.
- `LiveOrb` (animated only while speaking; respect `prefers-reduced-motion`),
  `LiveCaptions` (spoken words white, upcoming words grey), `LiveCardStack` — Live.

### Backend `ui_blocks` → component mapping
The backend returns `ui_blocks` in chat answers and tool results. Render them with:
`verdict` → Verdict header · `compare_bars` → `CompareBars` · `steps` → `ActionSteps` ·
`forecast_chart` → `ForecastChart` · `kpi` → `KpiCard` · `approval` → approve buttons.
The same renderer is used in Chat (inside `AnswerCard`) and in Live (right-hand cards).

## Writing style for AI text in the UI
Decision first, then one reason, then at most 3 steps. Plain Uzbek, no jargon
(no "stsenariy", "zaxira", "deterministik"). Examples are in `Chat.html` and `Live.html`.

## Demo data (the mockups use these; the seed dataset must reproduce them)
Café "Navro'z Kafe", today 2026-11-21, cash 48.2 mln UZS, minimum safe balance 10 mln.
Obligations: 25-Nov supplier 22.0; 1-Dec rent 15.0; 10-Dec salaries 45.0 + NBU loan 18.5;
15-Dec tax 8.0; 25-Dec supplier 22.0; 1-Jan rent 15.0; 10-Jan salaries 45.0 + loan 18.5;
15-Jan tax 8.0. Daily revenue by weekday (Mon→Sun, mln): 5.8, 5.9, 6.0, 6.2, 7.6, 8.9, 8.2;
variable costs 45 % of revenue.
Expected engine results: baseline lowest 18.8 on 10-Dec; buy 25 mln today → −6.2 on 10-Dec;
buy on 12-Jan → lowest 12.3 on 12-Jan; pay 9+8+8 in instalments → lowest 9.8;
revenue −20 % → −7.5 on 10-Jan; +2 staff (6 mln/month) → 12.8 on 10-Dec.

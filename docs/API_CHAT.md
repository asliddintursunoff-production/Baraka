# Chat API contract (M3)

Same origin, Django session cookie, `X-CSRFToken` header on POST (see `frontend/src/lib/api.ts`).
All display text comes from the backend (Uzbek, already formatted); the frontend never formats numbers.

## GET /api/chat/bootstrap
```json
{
  "conversation_id": 12,
  "business_name": "Navro'z Kafe",
  "brief": {"time": "08:00", "lead": "Xayrli tong! Bugun hammasi joyida. Faqat bitta narsa:",
            "strong": "10-dekabr qiyin kun bo'ladi", "rest": "— oylik va kredit bir kunga tushgan. Ungacha katta xarid qilmang."},
  "messages": [Message],              // history of this conversation, oldest first
  "chips": [{"id": "cash", "label": "Hozir qancha pulim bor?"},
            {"id": "revenue_drop", "label": "Savdo kamaysa nima bo'ladi?"},
            {"id": "staff", "label": "Yana 2 ta xodim olsam bo'ladimi?"}],
  "basis": Basis
}
```
`Message`:
```json
{"id": 5, "role": "user"|"assistant", "author": "Siz"|"Dilnoza (hisobchi)"|"AI CFO", "time": "10:41",
 "text": "…",                        // user text, or assistant plain text when there is no answer card
 "voice": {"duration": "0:06"}|null, // user message recorded by voice
 "answer": Answer|null}              // assistant structured answer (card)
```
`Basis` (right panel "Nimaga asoslandim"):
```json
{"items": [{"icon": "sheets"|"rules"|"segment", "title": "Sizning Google Sheets jadvallaringiz", "note": "yangilangan: bugun 09:12"}, ...],
 "confidence": {"label": "Yuqori"|"O'rtacha"|"Past", "level": "high"|"medium"|"low", "note": "Oylik va kredit sanalari aniq ma'lum."}}
```

## POST /api/chat/messages  → `text/event-stream`
Body: `{"text": "...", "conversation_id": 12}` or `{"chip": "cash", "conversation_id": 12}`
(optional `"voice": {"duration": "0:06"}` when the text came from the mic).

SSE events (each `event: <name>\ndata: <json>\n\n`):
| event | data | meaning |
|---|---|---|
| `meta` | `{"conversation_id", "user_message_id"}` | first event |
| `status` | `{"text": "Hisoblayapman…"}` | show a small status line |
| `blocks` | `{"blocks": [UiBlock], "replace": true}` | draw these cards **now** (before any text). A later `blocks` event replaces earlier ones. |
| `answer` | `Answer` | final structured answer |
| `done` | `{"message_id", "latency_ms", "model"}` | stream finished |
| `error` | `{"message": "Uzbek text"}` | show the message; the stream ends |

`Answer`:
```json
{"verdict": "yes"|"no"|"risky"|"info",
 "headline": "Yo'q, hozir olmang.",              // <= 60 chars, big coloured title
 "reason": "Agar hozir 25 million sarflasangiz, **10-dekabrda** xodimlarga oylik berishga 6,2 million so'm yetmay qoladi.",
 "steps": ["Jihozni **12-yanvarda** oling — ...", "..."],   // <= 3, may contain **bold**
 "blocks": [UiBlock],                           // the cards to show inside the answer (subset chosen by AI)
 "chips": ["Boshqa yo'l bormi?"],              // <= 3 follow-up questions
 "plan": {"id": 31, "summary": "12-yanvar 09:00 — jihoz xaridi eslatmasi", "status": "proposed"}|null,
 "candidate": {"id": 7, "text": "Agro Go'shtga to'lovni har doim 15 kun keyin deb hisoblayman.",
               "example": "Masalan, 25-noyabrdagi to'lov 10-dekabrga o'tadi.",
               "warning": "Lekin e'tibor bering: 10-dekabr yanada og'irlashadi. Shu kuni birinchi oylik va kreditni to'lang."}|null,
 "explain": ["Sizning 8 oylik jadvalingiz va 5 ta majburiy to'lov sanasi", "Har bir kunning qoldig'i alohida hisoblandi, AI raqamni o'zi o'ylab topmaydi", "..."],
 "speech": "Yo'q, hozir olmang. ...",          // text for the "Tinglash" button
 "model": "gemini-3.8-flash"|"template"}
```
`UiBlock` — already typed in `frontend/src/components/UiBlockRenderer.tsx` (`verdict`, `compare_bars`, `steps`, `kpi`, `forecast_chart`, `day_breakdown`, `approval`). In the answer card the verdict/reason/steps come from `Answer` itself; `blocks` usually holds `compare_bars` (and sometimes `forecast_chart`/`kpi`/`day_breakdown`).

## Actions on an answer
- **"Ha, shunday qilamiz"** → `POST /api/actions/{plan.id}/approve` → `{"id", "status": "approved", "summary"}` (idempotent).
- **"Boshqa yo'l bormi?"** → just send it as a normal message (`text`).
- **"To'g'ri, eslab qol"** → `POST /api/knowledge/candidates/{candidate.id}/accept` → `{"rule_id", "text_uz", "forecast_changed": true}`; **"O'zgartirish"** → focus the composer with the candidate text.
- **"Tinglash"** → `GET /api/chat/messages/{message_id}/speech` → `audio/wav` (play it; show a spinner until it loads).
- **Mic in composer** → record with `MediaRecorder` (≤ 30 s) → `POST /api/chat/transcribe` (raw body, `Content-Type: audio/webm` or `audio/ogg`) → `{"text": "...", "duration": "0:06"}` → send as a message with `voice`.
- **"Jonli gaplashish"** button → link to `/live`; on mouse-enter call `GET /api/live/session/prefetch` (fire and forget; M4).

# Google / Sources API contract (M5)

Same origin, session cookie, `X-CSRFToken` on POST. All texts arrive in Uzbek, already formatted.
Scopes: `openid email https://www.googleapis.com/auth/drive.file` only. The browser never sees a refresh token.

## OAuth
- `GET /api/integrations/google/status` →
  `{"connected": bool, "email": "x@gmail.com"|null, "needs_reauth": bool}`
- `GET /api/integrations/google/start?next=/onboarding/connect?step=pick` → 302 to Google (full-page navigation, not fetch).
- Google returns to `/api/integrations/google/callback`, which redirects to `next`. On error it redirects to
  `/onboarding/connect?error=<code>&message=<uz text>`. Codes: `access_denied` (user refused), `invalid_state`, `exchange_failed`.
- `POST /api/integrations/google/disconnect` → `{"ok": true}` (revokes and deletes the token).

## Picker
- `GET /api/integrations/google/picker-config` →
  `{"access_token": "...", "developer_key": "...", "app_id": "123456789", "expires_at": "ISO"}` (short-lived token).
- Frontend loads `https://apis.google.com/js/api.js` dynamically (Connect and Sources pages only), then `gapi.load('picker')`.
  - Views: Google Sheets plus `.xlsx`, multi-select (`Feature.MULTISELECT_ENABLED`), folders not selectable.
  - Settings: `setOAuthToken(access_token)`, `setDeveloperKey(developer_key)`, `setAppId(app_id)`, locale `uz`.
  - Title / instruction: "Jadvallaringizni belgilang (papkani emas)".
  - Picked file ids go to `POST /api/sources`.

## Sources
### `POST /api/sources` `{"file_ids": ["..."]}`
Checks each file on Drive, creates the sources, reads every sheet and proposes a mapping. Can take a few seconds: show "AI ustunlarni o'qiyapti…". Returns `Proposals`:
```json
{
  "sources": [{"id": 3, "title": "demo_navroz", "kind": "google_sheet"|"xlsx",
               "summary": "7 varaq: Kassa · Kirim · Chiqim · Oylik …",
               "sheets": [SheetProposal]}],
  "field_options": [{"value": "date", "label": "To'lov sanasi"}, …],
  "kind_options": [{"value": "transactions_out", "label": "Xarajatlar"}, …],
  "issues_preview": [{"source_id": 3, "sheet": "Chiqim", "row": 42,
                      "message": "Sana \"31.11.2026\" — noyabrda 31-kun yo'q", "action_label": "30.11 deb olish"}],
  "needs_opening_balance": false,
  "opening_balance_hint": {"amount_display": "48,2 mln", "date_display": "21-noyabr"}|null
}
```
`SheetProposal`:
```json
{"title": "Chiqim", "rows": 1248, "rows_display": "1 248", "header_row": 1,
 "kind": "transactions_out", "kind_label": "Xarajatlar",
 "recognized": "7 ustundan 6 tasi aniq tanildi",
 "columns": [{"index": 0, "header": "Sana", "sample": "14.11.2026", "field": "date", "field_label": "To'lov sanasi",
              "confidence": 0.97, "status": "sure"|"confirm", "question": "Haqiqiy to'lovmi yoki rejami?"|null}]}
```
Errors: `400 {"error": "no_access", "message": "…"}` when a file can't be opened. `409 {"error": "reauth_required", "message": "…"}` → show "Qayta ulash" (start the OAuth flow again).

### `POST /api/sources/confirm` → `text/event-stream`
Body:
```json
{"mappings": [{"source_id": 3, "sheet": "Chiqim", "kind": "transactions_out", "columns": {"0": "date", "1": "amount", "2": "category"}}],
 "opening_balance": {"amount": "48200000", "date": "2026-11-21"}|null,
 "auto_sync": true}
```
SSE events:
- `progress` `{"text": "3 ta varaq o'qildi…", "pct": 40}`
- `done` `{"text": "Prognoz tayyor", "redirect": "/"}`
- `error` `{"message": "…"}`

### `POST /api/sources/sync` → `text/event-stream`
"Hozir yangilash". Same events as confirm; `done` has no redirect, just refresh the page data.

### `GET /api/sources` (Ma'lumotlar page)
```json
{"connected": true, "email": "x@gmail.com", "needs_reauth": false,
 "status": {"ok": true, "title": "Hammasi ishlayapti",
            "subtitle": "Oxirgi tekshiruv: bugun 09:12 · har 15 daqiqada tekshiriladi · x@gmail.com"},
 "files": [{"source_id": 3, "label": "demo_navroz › Kirim", "kind_label": "Kirim (savdo)", "rows": "2 104",
            "state": "Yangi · +31"|"O'zgarish yo'q"|"Xato", "state_tone": "new"|"same"|"error"}],
 "issues": [{"id": 9, "message": "\"Chiqim\" varag'idagi 1 262-qatorda summa yozilmagan. Uni hisobga olmay turibman.",
             "action": "set_amount"|"use_suggestion"|"ignore", "action_label": "Summani kiritish"}],
 "log": [{"when": "Bugun 09:12", "text": "+46 qator · prognoz yangilandi", "tone": "success"|"muted"|"error"}]}
```
When `connected` is false or there are no files, show the empty state with "+ Yangi fayl ulash".

### Other endpoints
- `POST /api/sources/issues/{id}/resolve` `{"action": "use_suggestion"|"ignore"|"set_amount", "value": "350000"?}` → `{"ok": true}`
- `POST /api/sources/{id}/remap` → `Proposals` for that one source. "Ustunlarni qayta ko'rish" opens `/onboarding/connect?step=map&source={id}`, which shows step 3 with these proposals.

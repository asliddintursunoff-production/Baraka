# Charts (Part B) and CFO answers (Part D/E) — frontend contract

## Forecast block (`/api/dashboard` → `forecast`, `/api/forecast` → `forecast`)
Existing fields stay (`series`, `safe_min`, `safe_label`, `summaries`, `default_horizon`, `insufficient_data`). New:
```json
{
  "history": null | {
    "title": "O'tgan davr — haqiqiy",
    "points": [{"date": "2026-08-01", "close": "1321511131.18"}],      // daily actual closing cash, up to last_actual (12 months)
    "weekly": [{"week": "2026-07-27", "in": "98000000", "out": "71000000"}],
    "markers": [{"date": "2026-01-02", "label": "Ta'sischi kiritmasi 600,0 mln", "amount": "600000000"}],
    "last_actual": "2026-10-31",
    "caption": "31-oktyabr 2026 holatida kassa 1 439,5 mln; 3 oyda 118,0 mln o'sdi."
  },
  "title": "Prognoz — keyingi 60 kun",
  "start": "2026-10-31",            // the forecast starts at the last actual day
  "today": "2026-11-21",            // real today ("Bugun" marker)
  "gap": null | {"from": "2026-11-01", "to": "2026-11-21", "label": "Ma'lumot kiritilmagan"},
  "hardest": {"date": "2027-01-10", "label": "10-yanvar 2027, shanba", "balance": "139,6 mln",
              "payments": [{"title": "Ish haqi", "amount": "63,3 mln"}]},
  "caption": "Keyingi 60 kunda eng qiyin kun — 10-yanvar 2027: 139,6 mln qoladi. Xavfsiz chegaradan yuqori.",
  "beyond": ""                       // a worse day after the 60-day horizon, shown on its own line when non-empty
}
```
`series` points already carry `date`, `close`, `p10`, `p90` (strings, so'm) — see `src/lib/types.ts`.

## Chat answer (SSE)
New event before `answer`: `event: delta` `data: {"text": "…markdown chunk…"}` — append to the streaming message.
`answer` gains `markdown: string` (the full CFO answer, Uzbek markdown: `##`/`###` headings, `**bold**`, lists `- `, numbered `1. `, tables `| a | b |`).
When `markdown` is non-empty, it is the main content; `blocks` render below it, each with an optional `caption` (one line, "what to look at").

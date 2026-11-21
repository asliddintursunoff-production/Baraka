# Advisor answers + new blocks (contract)

Every number comes from the engine or from a user-confirmed assumption. The LLM never invents a number.

## Chat `answer` SSE event (existing fields stay)
```json
{
  "verdict": "info", "headline": "...", "reason": "...", "steps": ["..."], "blocks": [...], "chips": ["..."],
  "plan": null, "candidate": null, "explain": [], "speech": "...", "model": "...",
  "mode": "quick" | "advisor",
  "advisor": null | {
    "plan": [{"when": "25-noyabr", "action": "Tushlik setini boshlang (Du–Pa)", "amount": "1,2 mln"}],
    "assumptions": [{"text": "Qo'shimcha porsiya: 30 ta/kun", "editable": true, "key": "extra_units_per_day",
                     "value": "30", "tool": "investment_payback", "args": {"cost": "12000000", "extra_units_per_day": 30}}],
    "risks": ["≤ 2 strings"],
    "question": "optional single clarifying question" | null
  }
}
```
- `advisor.plan`: 3–6 dated steps for roadmap questions, ≤ 3 otherwise. Render as a vertical timeline (when · action · amount). When `advisor` is present, render `advisor.plan` instead of `steps`.
- `advisor.assumptions`: render as chips labelled "taxmin". When `editable`, a tap opens a small inline input prefilled with `value`. Submit → `POST /api/tools/{tool}` with `{...args, [key]: newValue}` (no LLM) → replace this message's `blocks` with `result.ui_blocks` and its assumptions with `result.assumptions`. Errors: show `result.error`/`detail` in Uzbek under the chip.
- `advisor.risks`: a short "Xavf" list. `advisor.question`: one clarifying question, shown above the chips.
- The chips stay as today (≤ 3 follow-ups that send a new message).

## Tool results (`POST /api/tools/<name>`, same envelope as today)
`{ok, facts, display, say, ui_blocks, assumptions: [...same shape as above...], answer: {verdict, headline, reason, steps}}`

New tools: `business_snapshot`, `when_can_afford`, `savings_goal`, `debt_payoff`, `investment_payback`, `revenue_growth_target`, `loan_affordability`, `compare_options`, `price_change`, `record_debt`.

## New ui_blocks (all amounts are preformatted display strings; never compute in the UI)
```json
{"type": "plan_timeline", "id": "...", "title": "...", "steps": [{"when": "25-noyabr", "action": "...", "amount": "22 mln", "tone": "info|success|warn|danger"}]}
{"type": "payback_chart", "id": "...", "title": "...", "points": [{"label": "0", "value": -30000000, "display": "−30,0 mln"}],
 "break_even_index": 9, "break_even_label": "9-oyda o'zini qoplaydi", "series": [{"name": "Asosiy", "points": [...]}]}
{"type": "scenario_table", "id": "...", "title": "...", "columns": ["Pessimistik", "Asosiy", "Optimistik"],
 "rows": [{"label": "Oylik sof foyda", "values": ["2,1 mln", "3,0 mln", "3,9 mln"]}], "highlight": 1}
{"type": "debt_list", "id": "...", "title": "...", "items": [{"counterparty": "Shavkat aka", "amount": "30,0 mln", "due": "15-dekabr", "note": "go'sht uchun", "tone": "warn"}], "total": "30,0 mln"}
{"type": "metric_grid", "id": "...", "title": "...", "items": [{"label": "Yalpi marja", "value": "58%", "note": "xarajat ulushi 42%", "tone": "success|warn|danger|muted"}]}
```
- `payback_chart.points[].value` is a plain number (so'm) only for drawing; labels always use `display`. Mark the break-even point. If `series` is present (3 cases), draw base solid and the others dashed.
- `scenario_table.highlight`: index of the recommended/base column.

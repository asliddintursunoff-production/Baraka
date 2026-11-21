# PROMPT — Implement the 100-question template catalogue (without touching Q1–Q4)

Attached file: `golden/AI_CFO_100_savol_shablonlar.md` (put it in the repo at `/golden/catalog/AI_CFO_100_savol_shablonlar.md`).

## 0. Goal

We already have 4 **presentation (golden) questions**, each with its own md, ReportCard, LiveReport, speech and side-question table:

| ID | File | Intent |
|---|---|---|
| Q1 | `golden/Q1_agregator_vs_ozdostavka.md` | `channel_economics` |
| Q2 | `golden/Q2_ishchi_olsam_oqlaydimi.md` | `hire_payback` |
| Q3 | `golden/Q3_lavash_aparat_olsam.md` | `equipment_investment` |
| Q4 | `golden/Q4_daromad_10_foiz_strategiya.md` | `revenue_growth_plan` |

Now add a **second tier: 100 catalogue intents** (S02–S48 and N01–N63 from the attached file). Each one gets:
- a deterministic tool;
- a ReportCard (chat) and the same card in Live;
- a short speech;
- side-question chips.

The catalogue does not have to be as polished as Q1–Q4, but every answer must be correct, computed from the user's file, and rendered as a real report: no plain text walls and no fake tables.

---

## 1. HARD RULE — Q1–Q4 are frozen and isolated (highest priority, never break)

Treat Q1–Q4 as a **protected zone**. Any violation of these rules means the task has failed.

### 1.1 Do not modify
- Do NOT edit `golden/Q1..Q4*.md`.
- Do NOT edit their tools, their calculation code, their ReportCard/LiveReport configs, their speech scripts or their side-question tables.
- Do NOT refactor shared helpers they use in a way that changes their output. If a shared helper must change, add a new function and leave the old one as is.
- **Snapshot test:** before you start, run Q1–Q4 on `Lazzat_Lavash_FastFood_2026.xlsx` and save their full JSON payloads as fixtures (`tests/golden_snapshots/Q1..Q4.json`). After every change, re-run them and diff. Any difference in numbers, verdict text, KPI, chart data or speech = **stop and revert**. This test runs on every commit and must be green before push.

### 1.2 Routing priority (3 tiers)
```
user message
  → Tier 1: GoldenRouter (Q1–Q4)        ← always checked FIRST
  → Tier 2: CatalogRouter (100 intents)  ← only if Tier 1 did not match
  → Tier 3: full-context chat (Gemini)   ← everything else
```
- Tier 1 keeps its current classifier and thresholds unchanged (≥0.75 answer, 0.5–0.75 clarifying question).
- **Catalog routing:** the catalogue may only win if **both** of these hold:
  - Golden confidence < 0.5 for all of Q1–Q4;
  - catalogue confidence ≥ 0.75.
- **Tie-break:** if any Q1–Q4 score is within 0.15 of the best catalogue score, Golden wins. When in doubt, Golden always wins.
- **Lexical guard:** if the message contains these markers, the catalogue is NOT allowed to answer; route to Golden (or ask which one):
  - Q1 markers: Yandex, Uzum, agregator, o'z dostavka, kuryer vs agregator.
  - Q2 markers: ofitsiant/ofitsant olsam, yangi ishchi olsam, xodim yollasam … oqlaydimi.
  - Q3 markers: apparat/aparat, uskuna/jihoz olsam, lavash apparat, fritur, pech olsam.
  - Q4 markers: daromadni X% oshirish, savdoni oshirish strategiyasi, revenue +10%.
- **Overlap test at build time:**
  - Embed every catalogue variant and compare it against every Q1–Q4 paraphrase.
  - If cosine ≥ 0.80, the build fails and lists the offending catalogue intent. Fix it by rewording the catalogue variant, never by changing Q1–Q4.
  - Also add negative tests: each Q1–Q4 paraphrase (all of them, plus 5 new natural variants each) must route to Golden, never to the catalogue.

### 1.3 Catalogue never calls Golden tools to answer
- Catalogue tools must not call `channel_economics`, `hire_payback`, `equipment_investment` or `revenue_growth_plan` to produce their own answer.
- They may read the same **shared facts** (cash forecast, capacity load, P&L) from one shared source, so the numbers stay identical across answers.
- When a catalogue answer naturally leads into a golden topic, it shows a **link chip** instead of answering, e.g. `"Apparat olsam-chi?" → opens Q3`. In the file this is marked as `→ Q3 (taqdimot savoli)`. The chip triggers the real Golden flow with its own card and speech.

### 1.4 One source of truth
These facts come from ONE shared module, used by both Golden and catalogue. They must never be recomputed differently:
- cash today;
- the tightest day (5 Dec) and its balance;
- loan balance and next payment;
- aggregator receivable;
- Saturday load / capacity and "ulgurmadi" days;
- monthly P&L lines;
- the payroll list.

If a catalogue answer shows the same fact as Q1–Q4, it must be the same number.

---

## 2. Q1–Q4 side questions — they must still work, fully

Isolation does not mean Golden goes silent after its first answer. During the presentation the jury will ask follow-ups. **Keep and extend the existing section-7 side-question logic of each golden file.**

### 2.1 Session context
- After a Golden answer, store `active_golden = {id, params, payload, ts}` in the session (chat and Live share it).
- Any follow-up within **10 turns or 15 minutes** that is not clearly a new topic is first checked against the active golden's side-questions.

### 2.2 Side-question handling (priority inside an active golden)

| Follow-up type | Example (Q3 active) | What to do |
|---|---|---|
| Parameter change | "80 mln bo'lsa-chi?", "36 oyga bo'lib olsam?", "stavka 28% bo'lsa?" | Re-run the SAME golden tool with new params. Show the same card + "Oldin → Yangi" table. Speech: 1–2 sentences about what changed. |
| Pre-computed side question (section 7.1 of the golden md) | "Kredit olsam oyiga qancha to'layman?", "Qachon olsam bo'ladi?" | Answer from the 7.1 table / recompute with the tool. Mini-card (KPI + 1 table). |
| "Nega / qanday hisobladi?" | "Nega 11 oyda?", "Bu raqam qayerdan?" | Explain the formula in plain Uzbek with the actual numbers and source sheet/column. No new tool call needed. |
| "Batafsil / yana" | "Batafsil ayt", "jadvalni ko'rsat" | Open the next sections of the same card (Live: next cue). |
| Cross-golden jump | Q3 active, user asks about Yandex | Switch to Q1 (full Golden flow). Set `active_golden = Q1`. |
| Related catalogue topic | Q3 active, user asks "kassam yetadimi o'sha kuni?" | Answer with a mini-card computed by the catalogue tool (N01/S18), then return to the Q3 context ("Q3 bo'yicha yana savol bormi?"). Do NOT change Q3's numbers. |
| Totally new topic | "Soliq kalendari?" | Clear `active_golden` and route normally (Tier 2/3). |

### 2.3 Rules for Golden side answers
- Never contradict the main golden answer. If new params change the verdict, say so explicitly: «Bu holatda xulosa o'zgaradi: …», and show both columns (Oldin / Yangi).
- Use the same units, rounding and wording as the main card.
- If a side question is not in 7.1 and cannot be computed:
  1. give a reasoned estimate (labelled "taxmin");
  2. ask one clarifying question.
  Never answer "ma'lumot yo'q" when the number can be computed or estimated.
- In Live, a side answer is short: 1–2 sentences, plus the card update on screen.

### 2.4 Tests for side questions
For each Q1–Q4, add ≥ 6 follow-up tests:
- 2 param changes;
- 2 from 7.1;
- 1 "nega";
- 1 cross-jump.

Assert:
- correct routing;
- Golden payload unchanged for the base case;
- the "Oldin → Yangi" table is present when params change.

---

## 3. Implement the 100 catalogue intents

### 3.1 Registry
- Parse `golden/catalog/AI_CFO_100_savol_shablonlar.md` into `CatalogRegistry`, using these fields for each question:
  - id, intent, variants, params, sources, calculation, report;
  - verdict template, KPI, chart, table, actions;
  - live speech, side chips.
- Load it at startup and cache it. Add a test that 100 intents load and that IDs and intents are unique.

### 3.2 Tools
- One deterministic tool per intent: `catalog/<intent>.py`. Use Decimal. Output is a JSON payload with these fields:
  `{verdict_vars, kpis[], chart, table, actions[], assumptions[], sources[], chips[]}`.
- Reuse the shared modules: `cash_forecast_daily`, `obligations_calendar`, `pnl_month`, `capacity_load`, `menu_economics`, `staff_costs`, `price_elasticity`, `loan_schedule`, `web_lookup` (with source + date).
- The LLM only writes the verdict sentence from the payload, and may not invent numbers. The Fact guard checks that every number in the text exists in the payload.
- Default period: the last closed month. The current open month is only a run-rate, labelled as such.

### 3.3 UI
- Use the same `ReportCard` component as Golden, in a "catalog" variant (slightly simpler: no hero animation).
- Sections:
  - Xulosa;
  - 3 KPI tiles (green/yellow/red);
  - chart (if specified);
  - table (if specified);
  - "Nima qilish kerak" (3 steps with so'm/date);
  - Taxminlar (editable → recompute);
  - Manba (sheet!column, rows, period);
  - chips.
- Live: show the same card immediately when the intent is recognised, then speak the 1–2 sentence `Live` line from the file. "Batafsil" opens the remaining sections.
- If there is an action → "Tasdiqlaysizmi?" → create Tasks/reminders (never move money).

### 3.4 Catalogue side questions
Same mechanism as Golden (`active_catalog = {id, params, payload}`): param change → recompute + "Oldin → Yangi"; chips from the file; "nega" → formula explanation. But **Golden side handling always has priority** if `active_golden` is set.

### 3.5 Rollout order (commit + push after each batch, snapshot test green)
1. Router tiers + guards + overlap/negative tests + Q1–Q4 snapshots (**no catalogue answers yet**).
2. S18, N01, N02, N03, N43, N42, N57, N53 (cash and forecast, the most useful for the demo).
3. N04–N15 (cash reserve, loans, financing).
4. N16–N27, N63 (capital, price/menu what-ifs).
5. N28–N49 (staff, costs, forecast).
6. N50–N62 (control, owner).
7. All S.. questions from the PDF.

---

## 4. Answer policy (MVP — applies to all tiers)

- **Answer maximally.** If data is not explicit:
  1. search every sheet by synonyms;
  2. compute it;
  3. if still missing, give an estimate with a range and labelled assumptions, plus one clarifying question.
- Say "ma'lumot yo'q" only for a truly absent exact fact (a phone number, a contract clause, a date that does not exist anywhere).
- Uzbek (Latin) replies. Numbers formatted as `71 121 526 so'm`; in speech, rounded and spoken.
- No hanging: if a tool fails, retry once, then fall back to Tier 3 with full context and say what was estimated. Never silently switch to another intent (the Q1 bug we had).

## 5. Bad-intent rule

Applies to messages like "biznesni qulatmoqchiman / uxlatmoqchiman / sindirmoqchiman", sabotage, hiding money from a partner, or tax fraud.
- Reply: **«Mening vazifam — biznesingizga foyda keltirish.»**
- Offer a legal alternative:
  - risk map (N60);
  - how to close or sell the business properly;
  - how to reduce losses.
- Do not lecture; keep it to 2 sentences.
- Note: «Biznesimni **nima** qulatishi mumkin?» is a legitimate risk question → N60, not a refusal.

## 6. Definition of done

- [ ] Q1–Q4 snapshot tests green (zero diffs) on every commit.
- [ ] Overlap test: no catalogue variant ≥ 0.80 cosine to any Q1–Q4 paraphrase.
- [ ] Negative tests: all Q1–Q4 paraphrases route to Golden.
- [ ] Q1–Q4 side-question tests (≥ 6 each) pass.
- [ ] 100 intents loaded, and each has a tool, a card and a Live line. At least 1 happy-path test per intent on the Lazzat file.
- [ ] Fact guard: no number in the text that is not in the payload.
- [ ] Shared facts identical between Golden and catalogue answers (test: cash today, tightest day, loan balance, Saturday load).

## 7. Workflow

- Work in batches (section 3.5). After each batch, run all tests, then `git add` the relevant files, commit with a clear message, and push.
- **Never commit `.env` or secrets.** Keep `GEMINI_API_KEY` in env only; never print it in logs or prompts.
- At the end, report:
  - which intents are done;
  - test results;
  - any catalogue intent you reworded because of overlap (old → new wording).

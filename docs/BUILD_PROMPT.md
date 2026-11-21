# Claude Code uchun loyiha topshirig'i

> Bu faylni loyiha ildizida `docs/BUILD_PROMPT.md` sifatida saqla va har bir bosqichdan oldin qayta o'qi.
> Dizayn: `design/DESIGN.md` va `design/pages/*.html`. Maxfiy kalitlar: `.env` (hech qachon commit qilinmaydi).

---

## 0. Sen kimsan va nima quryapmiz

Sen tajribali full-stack muhandissan. Hackathon uchun **ishlaydigan, tez va ishonchli MVP** quryapmiz.

**Mahsulot:** O'zbekistondagi kichik bizneslar (birinchi navbatda kafe va do'konlar) uchun **shaxsiy AI moliyaviy direktor (AI CFO)**. U:
1. biznesning Google Sheets jadvallarini **bir marta ulanganidan keyin o'zi** o'qib boradi (jadval tuzilishi istalgancha bo'lishi mumkin);
2. har kunlik kassa qoldig'ini oldindan hisoblaydi va **xavfli kunni o'zi topib, foydalanuvchiga o'zi aytadi**;
3. "25 mln sarflasam, oylikka yetadimi?" degan savolga **aniq qaror** beradi: "Yo'q, hozir olmang. 12-yanvarda oling." — sababi va 3 tadan ko'p bo'lmagan qadam bilan;
4. matn **va jonli o'zbekcha ovoz** orqali gaplashadi, gapirayotganda grafik va kartalar chizadi;
5. xodimlar tuzatishlaridan **o'rganadi** va shu biznesga moslashadi; shu turdagi boshqa bizneslardan **anonim, umumlashtirilgan** bilim oladi — lekin ma'lumotlar hech qachon aralashmaydi;
6. har qanday amalni (reja, eslatma) **faqat foydalanuvchi tasdig'idan keyin** bajaradi. Real pul o'tkazmasi yo'q.

**Mahsulot nomi dinamik:** hamma joyda `APP_NAME` env o'zgaruvchisidan olinadi (UI, `<title>`, AI system prompt, xabarlar). Kodda nom hech qayerda qattiq yozilmaydi. Default: `BizPilot AI`.

---

## 1. O'zgarmas tamoyillar (buzilmasin)

1. **Raqamni faqat Financial Engine hisoblaydi.** LLM hech qachon arifmetika qilmaydi, balans/summa/sana o'ylab topmaydi. LLM: savolni tushunadi, tool tanlaydi, tool natijasini sodda tilda tushuntiradi.
2. **Pul = `Decimal`**, bazada `NUMERIC(18,2)`. `float` pul uchun taqiqlangan (faqat engine ichidagi vektorlashtirilgan hisobda numpy `int64` tiyin sifatida ishlatish mumkin, chiqishda `Decimal`ga qaytariladi).
3. **Multitenant:** har bir biznes ma'lumoti `business_id` bilan ajratilgan. Bir biznes boshqasining birorta qatorini hech qanday yo'l bilan ko'rmaydi — na API, na LLM konteksti, na vektor qidiruvi orqali.
4. **Tool argumentlarida `business_id` yo'q.** Biznes har doim sessiyadan olinadi. Modeldan kelgan har bir argument backend'da validatsiya qilinadi.
5. **Kechikish — birinchi darajali talab** (6-bo'lim). Har bir yangi funksiya kechikish byudjetiga sig'ishi kerak.
6. **Ortiqcha infratuzilma yo'q:** Celery, Redis, Kafka, Kubernetes, alohida vektor DB (Qdrant va h.k.), mikroservislar, LangChain — **ishlatilmaydi**. Vektor qidiruv = PostgreSQL **pgvector**.
7. **UI matni o'zbekcha (lotin)**, `design/` dagi so'zma-so'z. AI javob uslubi: **avval qaror → bitta sabab → ko'pi bilan 3 qadam**, atamalarsiz ("stsenariy", "zaxira", "deterministik" kabi so'zlar foydalanuvchiga chiqmaydi).
8. **Halollik:** ma'lumot yetarli bo'lmasa "ma'lumot yetarli emas" deyiladi, taxminiy raqam ko'rsatilmaydi. Ishonch darajasi faqat engine hisoblagan metrikadan olinadi, LLM'dan emas.

---

## 2. Texnologiyalar (faqat shular)

**Backend:** Python 3.12, Django 5.x, Django REST Framework, ASGI (uvicorn worker'lari bilan gunicorn), psycopg 3 (connection pool), `pgvector` (Python paketi + Postgres extension), `google-genai` (rasmiy Gemini SDK, async client `client.aio`), `google-api-python-client` + `google-auth-oauthlib` (faqat Sheets), `numpy`, `pandas` (faqat ingestion/normalizatsiya va tunggi hisoblarda — so'rov yo'lida emas), `cryptography` (Fernet), `pytest` + `pytest-django`.

**Frontend:** Vite + React 18 + TypeScript, Tailwind CSS, shadcn/ui, Recharts, TanStack Query, React Router, `lucide-react`, `@google/genai` (brauzerda Live uchun).

**Ma'lumotlar bazasi:** PostgreSQL 16 + pgvector (lokal: `pgvector/pgvector:pg16` image).

**Deploy (Railway), xizmatlar soni minimal:**
- `web` — bitta Docker image: Django API **va** yig'ilgan React statikasi (WhiteNoise orqali). Frontend va API **bir domen**da → CORS yo'q, sessiya cookie oddiy ishlaydi, brauzer ↔ API ulanishi qayta ishlatiladi (kechikish uchun ham foydali).
- `scheduler` — **xuddi shu image**, boshqa start buyrug'i: `python manage.py run_scheduler`.
- `postgres` — Railway Postgres (pgvector yoqilgan).
Boshqa xizmat qo'shilmaydi.

**Lokal ishlab chiqish:** `docker-compose.yml` faqat `db` uchun. Backend va Vite lokal ishga tushadi; Vite dev server `/api` ni Django'ga proxy qiladi. `Makefile`: `make db`, `make dev`, `make test`, `make seed`, `make latency`.

---

## 3. `.env` — faqat shu 8 ta o'zgaruvchi

`.env.example` yarat (qiymatlarsiz) va `settings.py` faqat shularni o'qisin:

```
APP_NAME=BizPilot AI
APP_URL=http://localhost:8000          # OAuth redirect, ALLOWED_HOSTS, CSRF uchun
DEBUG=true
DJANGO_SECRET_KEY=
DATABASE_URL=postgres://...
GEMINI_API_KEY=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

Qoidalar:
- Boshqa sozlamalar (model ID'lari, sync intervali, minimal xavfsiz qoldiq default'i, horizon'lar) — kodda **bitta** `config/app_settings.py` modulida konstanta sifatida. Env'ga qo'shilmaydi.
- Google refresh token'larni shifrlash kaliti `DJANGO_SECRET_KEY` dan HKDF orqali olinadi (alohida env yo'q).
- `GEMINI_API_KEY` faqat backend'da. Brauzerga **hech qachon** yuborilmaydi (Live uchun ephemeral token ishlatiladi). Kalitni logga, xato xabariga, commit'ga yozma.
- `APP_NAME` frontend'ga Django `index.html` render qilganda `window.__APP_CONFIG__ = {"appName": ...}` sifatida beriladi; React uni sidebar, `document.title`, Live sarlavhasi va hamma joyda ishlatadi.

---

## 4. AI modellari (default'lar — boshlashdan oldin tekshir)

`config/app_settings.py`:
```python
AI_MODELS = {
    "chat": "gemini-3.8-flash",          # chat orchestrator, tool calling, structured output
    "light": "gemini-3.5-flash-lite",    # ogohlantirish matni, suhbat xulosasi, qoida ajratish
    "mapping": "gemini-3.8-flash",       # jadval ustunlarini tanish (bir martalik)
    "live": "gemini-3.8-live",           # jonli ovoz (native audio)
    "embedding": "gemini-embedding-001", # pgvector uchun
}
EMBEDDING_DIM = 768   # output_dimensionality=768; vektorni L2-normallashtirib saqla
```

- Ishni boshlashdan oldin `python manage.py check_ai` buyrug'ini yoz: `.env` dagi kalit bilan `models.list` chaqiradi, yuqoridagi har bir ID mavjudligini va Live/embedding ishlashini tekshiradi; yo'q bo'lsa aniq xato bilan to'xtaydi.
- Gemini API tez o'zgaradi: Live sessiya konfiguratsiyasi, ephemeral token (`auth_tokens.create`, hozir `v1alpha`), `Behavior.NON_BLOCKING`, `FunctionResponse.scheduling` (`WHEN_IDLE` / `INTERRUPT` / `SILENT`), transkripsiya sozlamalari, thinking darajasi parametrining aniq nomi — kod yozishdan oldin **ai.google.dev rasmiy hujjatidan tekshir** va topganingni `docs/AI_NOTES.md` ga yoz.
- Chat modeli uchun **eng past thinking darajasi** (tezlik uchun). Live uchun `extended-thinking` varianti ishlatilmaydi.

---

## 5. Arxitektura

**Bitta Django modular monolith**, uchta kirish nuqtasi:
1. **REST/SSE API** (brauzer → Django),
2. **scheduler jarayoni** (fon ishlari),
3. **Gemini Live** — brauzer Live API'ga **to'g'ridan-to'g'ri** WebSocket orqali ulanadi; Django faqat ephemeral token beradi va tool chaqiruvlarini bajaradi. Audio Django orqali **o'tmaydi**.

### 5.1 Papka tuzilishi
```
backend/
  config/            settings.py, urls.py, asgi.py, app_settings.py
  apps/
    tenancy/         User, Business, Membership, TenantMiddleware, TenantScopedManager
    integrations/    Google OAuth, SheetsClient (interfeys) + GoogleSheetsClient + FakeSheetsClient (testlar)
    ingestion/       sheet tanish, header aniqlash, mapping, normalizatsiya, validatsiya, sync
    finance/         Transaction, Obligation, Counterparty, CashAccount
    engine/          TOZA PYTHON: Django import QILMAYDI
    insights/        xavf qoidalari, Alert, daily brief
    knowledge/       BusinessRule, RuleCandidate, ForecastParams, ForecastAccuracy, SegmentStats, MemoryItem (pgvector)
    ai/              gemini client, tools registry, promptlar, chat orchestrator, live token, uz_format
    actions/         ActionPlan (reja/eslatma), tasdiqlash, AuditLog
    telemetry/       LatencyEvent, Server-Timing middleware, latency_report
  manage.py
frontend/            Vite app
design/              (berilgan)
docs/                BUILD_PROMPT.md, PLAN.md, AI_NOTES.md, LATENCY.md
Dockerfile           multi-stage: node build → python runtime
docker-compose.yml   faqat db
Makefile, .env.example, README.md
```

### 5.2 Ma'lumotlar modeli (asosiy)
Barcha biznes jadvallarida `business` FK + indeks. Sanalar `DATE` (Asia/Tashkent), vaqt belgilari UTC.

- `Business(name, kind: cafe|shop|restaurant|pharmacy|other, city, safe_min_balance Decimal default 10_000_000, timezone, segment_key)`
- `Membership(user, business, role: owner|accountant|viewer)`
- `DataSource(business, spreadsheet_id, title, status, last_synced_at, last_error)`; `GoogleCredential(business, encrypted_refresh_token, scopes)`
- `SheetMapping(source, sheet_title, header_row, header_signature, sheet_kind, column_map JSON, confidence JSON, confirmed_by, confirmed_at)`
- `RawRow(source, sheet_title, row_index, row_hash, values JSON, status: active|deleted|ignored)` — unique `(source, sheet_title, row_hash)`
- `DataIssue(business, raw_row, kind, message_uz, suggestion JSON, status)`
- `Counterparty(business, name, kind)`
- `Transaction(business, amount, direction: in|out, category, counterparty, txn_date, method, raw_row, is_actual=True)`
- `Obligation(business, title, amount, due_date, expected_date, priority: critical|deferrable|discretionary, recurrence JSON|null, counterparty, status: planned|paid|cancelled, source: sheet|rule|manual)`
- `CashAccount(business, opening_balance, as_of_date)` (boshlang'ich qoldiq jadvalda bo'lmasa onboarding'da bir marta so'raladi)
- `ForecastSnapshot(business, created_at, horizon_days, daily JSON[{date, open, inflow, outflow, close, p10, p90}], min_balance, min_date, first_shortage_date, verdict, inputs_hash)`
- `Alert(business, kind, severity: info|warn|danger, date, amount, text_uz, dedupe_key UNIQUE, status: new|seen|dismissed, snapshot)`
- `BusinessRule(business, type, target JSON, effect JSON, text_uz, source: user|ai_confirmed, author, enabled, created_at)`
- `RuleCandidate(business, proposed JSON, text_uz, origin: correction|pattern, status: pending|accepted|rejected)`
- `ForecastParams(business, weekday_factors JSON[7], variable_cost_ratio, updated_at)`
- `ForecastAccuracy(business, week_start, mape, n_days)`
- `SegmentStats(segment_key, metric, value JSON, n_businesses)` — **biznesga bog'lanmagan**, faqat `n_businesses >= 5` bo'lsa yoziladi
- `MemoryItem(business NULL=global, kind: rule|note|correction|conversation_summary|segment_insight, text, embedding vector(768), meta JSON, created_at)` — HNSW indeks (cosine)
- `Conversation`, `Message(role, content, ui_blocks JSON, tool_calls JSON, latency_ms)`
- `ActionPlan(business, kind: reminder|spending_limit|purchase_plan, payload JSON, status: proposed|approved|done|cancelled, idempotency_key UNIQUE, proposed_by: ai, approved_by, approved_at)`
- `AuditLog(business, actor, event, tool, args JSON, result_hash, created_at)`
- `LatencyEvent(business, channel: voice|chat|api, name, ms, meta JSON, created_at)`

**Tenant izolyatsiyasi:** `TenantScopedManager` joriy biznesni context var'dan oladi; kontekst yo'q bo'lsa `objects` **xato** beradi (scheduler va migratsiyalar uchun alohida `unscoped` manager). Har bir app uchun "boshqa biznes ma'lumotini ko'ra olmaydi" degan test majburiy.

### 5.3 Financial Engine (`apps/engine`) — loyihaning yuragi
Toza funksiyalar, kirish/chiqish — `@dataclass(frozen=True)`. Django, ORM, tarmoq yo'q.

```python
@dataclass(frozen=True)
class EngineInput:
    today: date
    opening_balance: Decimal
    history: list[DailyActual]          # oxirgi ≥ 8 hafta: date, inflow, outflow
    obligations: list[ObligationIn]     # amount, due_date, priority, title, counterparty
    rules: list[RuleIn]                 # tasdiqlangan BusinessRule'lar
    params: ParamsIn                    # weekday_factors, variable_cost_ratio
    segment_prior: SegmentPriorIn|None
    safe_min: Decimal

def forecast(inp: EngineInput, horizon_days: int) -> ForecastResult
def simulate(base: ForecastResult, inp: EngineInput, change: Change) -> ScenarioResult
def evaluate_purchase(inp, amount, on_date=None, installments=None) -> PurchaseDecision
def explain_day(base: ForecastResult, day: date) -> DayBreakdown
def spend_limit_until(base: ForecastResult, until: date) -> Decimal
```

Hisob qoidalari:
- **Kunlik** model: `close(t) = close(t−1) + inflow(t) − outflow(t)`. Oylik "daromad − xarajat" emas — to'lov **sanasi** muhim.
- Tushum: oxirgi 8 hafta, hafta kuni bo'yicha o'rtacha × `weekday_factors`. Tarix < 8 hafta bo'lsa segment prior bilan aralashtiriladi: `w_segment = 1 − min(1, weeks/8)`. Tarix < 2 hafta va segment yo'q bo'lsa → `insufficient_data=True`, verdict chiqarilmaydi.
- O'zgaruvchan xarajat: `variable_cost_ratio × tushum`. Majburiy to'lovlar — aniq sanasida.
- Qoidalar prognozdan **oldin** qo'llanadi. MVP qoida turlari: `payment_shift(counterparty, days)`, `recurring(title, amount, day_of_month, priority)`, `weekday_factor(weekday, multiplier, period)`, `priority(target, level)`, `ignore(category|counterparty)`.
- Noaniqlik oralig'i: hafta kuni bo'yicha tarixiy qoldiqlarning (residual) standart chetlanishidan, `σ·√t` bilan kumulyativ; P10/P90. Bu "ishonch" ning yagona manbai.
- **Verdict (qat'iy qoida, LLM emas):**
  - `no` — horizon ichida kamida bitta `critical` to'lovdan keyin qoldiq < 0;
  - `risky` — hammasi yopiladi, lekin minimal qoldiq < `safe_min`;
  - `yes` — minimal qoldiq ≥ `safe_min`.
- `evaluate_purchase` alternativa qidiradi: (a) horizon ichida verdict `yes` bo'ladigan **eng erta sana**; (b) 3 oyga teng bo'lib to'lash; natijada `recommended` + `alternatives`.
- `spend_limit_until`: eng qiyin kungacha ixtiyoriy xarajat chegarasi = `min_balance − safe_min`, **1 mln ga pastga yaxlitlanadi** (18,8 − 10 = 8,8 → "8 mln").
- Ishlash: bazaviy kunlik qator numpy vektor; `simulate` faqat delta qo'shadi → **bitta simulyatsiya < 5 ms** (benchmark test).

**Oltin test'lar (majburiy, `design/DESIGN.md` "Demo data" bilan aynan):** bugun 2026-11-21, kassa 48,2 mln, safe_min 10 mln, hafta kunlari tushumi (Du→Ya, mln) 5.8, 5.9, 6.0, 6.2, 7.6, 8.9, 8.2, o'zgaruvchan xarajat 45%, to'lovlar DESIGN.md dagidek. Kutiladigan natijalar:
| Holat | Natija |
|---|---|
| bazaviy | eng past **18,8** mln, 2026-12-10, verdict `yes` |
| bugun 25 mln xarid | **−6,2** mln, 2026-12-10, verdict `no` |
| 2027-01-12 da xarid | eng past **12,3** mln, 2027-01-12, `yes` |
| 9+8+8 bo'lib to'lash (21-noy, 21-dek, 21-yan) | eng past **9,8** mln, `risky` |
| tushum −20% | **−7,5** mln, 2027-01-10, `no` |
| +2 xodim (oyiga 6 mln, 10-sanada) | **12,8** mln, 2026-12-10, `yes` |
| `spend_limit_until(2026-12-10)` | **8 000 000** |
| `evaluate_purchase(25 mln)` tavsiyasi | `no`, tavsiya sanasi **2027-01-12** (o'sha kuni yoki undan keyingi eng erta `yes` kun; agar algoritm boshqa sana topsa, sababini `docs/PLAN.md` ga yoz va men bilan kelish) |

### 5.4 Tool'lar (chat va Live uchun **bitta** to'plam)
`apps/ai/tools.py` da registry: har bir tool = nom, o'zbekcha tavsif, JSON sxema, handler. Bir xil deklaratsiya ham chat modeliga, ham Live sessiyasiga beriladi.

| Tool | Argumentlar | Vazifasi |
|---|---|---|
| `get_cash_status` | — | hozirgi kassa, bugungi holat, eng qiyin kun |
| `get_forecast` | `horizon_days ∈ {7,30,60,90}` | kunlik qator (qisqartirilgan), min, verdict |
| `get_upcoming_payments` | `days ≤ 90` | majburiy to'lovlar ro'yxati |
| `evaluate_purchase` | `amount`, `date?`, `installments?` | xarid qarori + tavsiya + alternativalar |
| `simulate_change` | `kind ∈ {revenue_pct, new_staff, extra_expense, payment_delay}`, `value`, `start_date?`, `counterparty?` | "agar..." |
| `explain_day` | `date` | o'sha kun: boshida, kirim, har bir to'lov, oxirida |
| `propose_plan` | `kind`, `date?`, `amount?`, `note?` | `ActionPlan(status=proposed)` yaratadi, **bajarmaydi** |
| `confirm_plan` | `plan_id` | faqat foydalanuvchi aniq "ha" degandan keyin; reja shu biznesniki va `proposed` bo'lishi shart; idempotent |
| `remember_fact` | `text` | `RuleCandidate(pending)` yaratadi; foydalanuvchi UI'da tasdiqlaydi |

**Har bir tool javobi bir xil shaklda** (≤ 2 KB, tez seriyalash):
```json
{
  "ok": true,
  "verdict": "no",
  "facts": {"shortage_date": "2026-12-10", "lowest_balance": "-6200000.00", "recommended_date": "2027-01-12"},
  "display": {"lowest_balance": "−6,2 mln", "recommended_date": "12-yanvar"},
  "speech":  {"lowest_balance": "minus olti million ikki yuz ming so'm", "shortage_date": "o'ninchi dekabr", "recommended_date": "o'n ikkinchi yanvar"},
  "ui_blocks": [
    {"id": "b1", "type": "verdict", "status": "no", "headline": "Yo'q, hozir olmang."},
    {"id": "b2", "type": "compare_bars", "title": "10-dekabr, oylik kuni kassada qancha qoladi?",
     "rows": [{"label": "Hozir olsangiz", "value": "-6200000", "display": "−6,2 mln", "status": "bad", "status_text": "Yetmaydi"},
              {"label": "12-yanvarda olsangiz", "value": "18800000", "display": "+18,8 mln", "status": "ok", "status_text": "Yetadi"}]},
    {"id": "b3", "type": "steps", "items": ["Jihozni 12-yanvarda oling — yanvar oyligi va kredit to'langandan keyin.", "10-dekabrgacha 8 million so'mdan katta xarid qilmang.", "12-yanvar ertalab sizga o'zim eslataman."]}
  ],
  "proposed_plan": {"id": "…", "summary": "12-yanvar 09:00 — jihoz xaridi eslatmasi"},
  "insufficient_data": false
}
```
- `display` va `speech` matnlari `apps/ai/uz_format.py` da **deterministik** yasaladi: `format_mln(6200000) → "6,2 mln"`, `uz_number_words(6200000) → "olti million ikki yuz ming"`, `uz_ordinal_date(date(2026,12,10)) → "o'ninchi dekabr"`, kesimli shakllar ("10-dekabrda"). Har biriga unit test (0, 1, 15, 100, 1 000, 2 500 000, 6 200 000, 18 800 000, 63 500 000, manfiy sonlar; oy nomlari).
- `ui_blocks` turlari: `verdict`, `compare_bars`, `steps`, `forecast_chart`, `kpi`, `day_breakdown`, `approval`. Ularni **backend tool natijasidan** yasaydi; LLM blok yaratmaydi, faqat qaysilarini ko'rsatishni tanlaydi.

### 5.5 Chat oqimi (`POST /api/chat/messages`, javob **SSE**)
1. Parallel (`asyncio.gather`): (a) savolni embedding qilib `MemoryItem` dan top-6 (shu biznes + global segment) olish, (b) `get_cash_status` keshdan.
2. Chat modeli (`AI_MODELS["chat"]`, minimal thinking) — system prompt + qisqa kontekst + tool'lar. Ko'pi bilan **3** tool raund.
3. Tool tugashi bilan darhol SSE `blocks` hodisasi → frontend grafik/kartani **LLM matnidan oldin** chizadi.
4. Yakuniy javob **structured output** sxemasida:
   ```json
   {"verdict": "yes|no|risky|info", "headline": "≤ 60 belgi", "reason": "bitta jumla",
    "steps": ["≤ 3 ta"], "show_blocks": ["b2"], "chips": ["≤ 3 ta keyingi savol"]}
   ```
5. **Raqam qo'riqchisi:** `headline/reason/steps` dagi har bir raqam/sana tool `display`/`facts` qiymatlaridan birortasiga mos kelishi kerak (regex + normalizatsiya). Mos kelmasa — bir marta qayta so'raladi, yana bo'lmasa — `ui_blocks` dagi tayyor shablon matni ishlatiladi.
6. SSE hodisalari: `status` ("Hisoblayapman…"), `blocks`, `answer`, `done`, `error`. Saqlash: `Message` + `AuditLog`.
7. **Tezkor yo'l:** composer'dagi tayyor chip'lar ("Hozir qancha pulim bor?" va h.k.) LLM'siz to'g'ridan-to'g'ri tool + shablon matn bilan javob beradi.

### 5.6 Jonli ovoz oqimi (eng muhim kechikish yo'li)
**Backend:** `POST /api/live/session` →
- `auth_tokens.create` (uses=1, ~30 daqiqa amal qiladi, yangi sessiya ochish oynasi ~1 daqiqa) bilan ephemeral token; **`liveConnectConstraints`** ga qulflanadi: `model = AI_MODELS["live"]`, javob modalligi AUDIO, kirish va chiqish audio transkripsiyasi yoqilgan, system instruction, tool deklaratsiyalari.
- System instruction ichiga **oldindan yuklangan qisqa kontekst** (≤ 1 500 token): `APP_NAME`, biznes nomi, bugungi sana, hozirgi kassa, eng qiyin kun, keyingi 5 ta majburiy to'lov, eng muhim 10 ta tasdiqlangan qoida/eslatma. **Ovoz yo'lida embedding yoki qidiruv chaqirilmaydi.**
- Javob: `{token, model, expires_at}`.

**Live system instruction (o'zbekcha, qat'iy):**
- Faqat o'zbek tilida (lotin) gapir; foydalanuvchi ruscha so'z ishlatsa ham.
- Avval qaror, keyin bitta sabab, keyin ko'pi bilan 3 qadam. Bir navbatda ko'pi bilan 3 jumla.
- Har qanday raqam, summa yoki sanani aytishdan oldin tool chaqir; raqamlarni **faqat `speech` maydonidan** o'qi, o'zing hisoblama va o'zgartirma.
- Tool natijasini kutayotganda bitta qisqa ibora ayt ("Hozir hisoblayman") va jim tur.
- Reja taklif qilganda "Shunday reja tuzaymi?" deb so'ra; foydalanuvchi "ha" desa `confirm_plan` ni chaqir; aks holda hech narsa bajarma.
- Bilmagan narsani o'ylab topma; "bu ma'lumot jadvalingizda yo'q" de.
- Kichik terminlar lug'ati (kassa, majburiy to'lov, oylik, kredit, ta'minotchi, xavfsiz chegara) — bir xil so'zlar ishlatilsin.

**Frontend (`/live`):**
- Sahifa ochilishi bilan **parallel**: `getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}})`, `POST /api/live/session`, AudioWorklet modullarini yuklash. Token kelishi bilan `ai.live.connect(...)` — foydalanuvchi gapirishidan **oldin** sessiya tayyor turadi. Chat sahifasida "Jonli gaplashish" tugmasiga sichqoncha borganda token oldindan olinadi (prefetch).
- Mikrofon: AudioWorklet → 16 kHz, 16-bit PCM, little-endian, **20–40 ms bo'laklar** bilan uzluksiz yuborish (bufer to'plab kutma).
- Ijro: 24 kHz PCM, AudioWorklet ring-buffer; **birinchi bo'lak kelishi bilan** ijro boshlanadi.
- Barge-in: server `interrupted` yuborsa — ijro buferini **darhol** tozalash; foydalanuvchi gapira boshlaganda AI ovozi to'xtaydi.
- `toolCall` kelganda: `fetch('/api/tools/<name>', {keepalive:true})` (bir domen, sessiya cookie) → natijadagi `ui_blocks` ni **darhol** o'ng panelda chizish → `sendToolResponse` (`id`, `name`, `response`). Engine tool'lari tez bo'lgani uchun `WHEN_IDLE` va `INTERRUPT` scheduling'ini o'lcha, p95 bo'yicha yaxshisini default qil (natijani `docs/LATENCY.md` ga yoz).
- Subtitr: kiruvchi va chiquvchi transkripsiyadan; AI aytgan so'zlar oq, qolgani kulrang (`design/pages/Live.html`).
- Uzilish/qayta ulanish: sessiya yopilsa yangi token bilan avtomatik qayta ulanish; xatoda "Yozib so'rash" rejimiga o'tish taklifi.
- Live tugagach: transkript + ko'rsatilgan bloklar `Conversation` ga saqlanadi (`POST /api/live/finish`), qisqa xulosa `light` model bilan **fonda** yoziladi va `MemoryItem` ga embedding qilinadi.

**Tool endpoint (`POST /api/tools/<name>`) talablari:**
- Biznes **sessiyadan**; argumentlar sxema bo'yicha validatsiya.
- Bazaviy prognoz **xotiradagi keshdan** (har biznes uchun `inputs_hash` bo'yicha; sync yoki qoida o'zgarganda bekor qilinadi). Kesh bo'lmasa — oxirgi `ForecastSnapshot` dan.
- So'rov yo'lida: LLM yo'q, embedding yo'q, tashqi tarmoq yo'q. Faqat 1–2 ta indeksli SELECT + engine.
- `Server-Timing` sarlavhasi; `AuditLog` yozuvi.

### 5.7 Google Sheets ingestion (istalgan tuzilishdagi jadval)
**Ulash (bir marta), `/onboarding/connect`:**
- OAuth scope'lar: `openid email https://www.googleapis.com/auth/spreadsheets.readonly`. Drive scope **yo'q**. Google Cloud'da OAuth "Testing" rejimi + test foydalanuvchilar (hackathon uchun yetarli; README'da qadamma-qadam yoz).
- Foydalanuvchi bir yoki bir nechta jadval **havolasini** qo'yadi (fayl soni cheklanmagan). `spreadsheets.get` bilan barcha varaqlar topiladi.
- Har bir varaq uchun: bo'sh qatorlarni o'tkazib **header qatorini avtomatik topish** (birinchi qator bo'lishi shart emas), 20 ta namuna qator → `mapping` model **structured output** bilan:
  `sheet_kind ∈ {transactions_in, transactions_out, transactions_mixed, obligations_schedule, payroll, loan_schedule, counterparties, ignore}`, har bir ustun → kanonik maydon (`date, amount, direction, category, counterparty, due_date, method, status, note, ignore`) + `confidence 0..1`. Sarlavhalar o'zbek, rus (kirill) yoki ingliz tilida bo'lishi mumkin.
- `confidence < 0.8` bo'lgan ustunlar UI'da "Tasdiqlang" bilan ko'rsatiladi; qolganlari avtomatik. Foydalanuvchi bir marta tasdiqlaydi → `SheetMapping`. Boshlang'ich kassa qoldig'i topilmasa — bitta savol.
- Ekran: `design/pages/Connect.html`.

**Normalizatsiya (LLM'siz, toza Python, har biriga test):**
- Summalar: `4 350 000`, `4,350,000`, `4.350.000`, `4350000 so'm`, `4,35 mln`, `-4 350 000`, `(4 350 000)`; valyuta belgisi.
- Sanalar: `14.11.2026`, `14/11/2026`, `2026-11-14`, `14 noyabr 2026`, `14 ноября`, Google Sheets serial raqami.
- Yo'nalish: alohida "Kirim/Chiqim" ustunlari, bitta ustundagi ishora yoki "Turi" ustuni.
- Kategoriya va kontragent nomlarini tozalash (bo'sh joy, registr, kirill/lotin).
- Takror qatorlar, bo'sh summa, mavjud bo'lmagan sana (31.11), noaniq yo'nalish → `DataIssue` (o'zbekcha xabar + taklif), **jimgina taxmin qilinmaydi**.

**Avtomatik sync (scheduler, har 15 daqiqada):**
- Har bir faol manba uchun `pg_try_advisory_lock(source_id)`; varaq qiymatlarini `values.batchGet` bilan o'qish; `row_hash` bo'yicha diff (yangi → qo'shiladi, yo'qolgan → `deleted`, o'zgargan = o'chirish + qo'shish).
- Header imzosi o'zgarsa yoki yangi varaq/ustun paydo bo'lsa → faqat o'sha varaq uchun qayta mapping; ishonch past bo'lsa foydalanuvchiga savol (`DataIssue`), aks holda avtomatik.
- O'zgarish bo'lsa: engine → `ForecastSnapshot` → `insights.evaluate` → keshni bekor qilish.
- Sheets API kvotasini hurmat qil (eksponensial backoff); xato bo'lsa `DataSource.last_error` va UI'da "Ma'lumotlar" sahifasida ko'rinadi.

### 5.8 Proaktiv ogohlantirishlar (`apps/insights`)
- Qoidalar (deterministik): `critical` to'lov kuni qoldiq < 0 (`danger`); minimal qoldiq < `safe_min` (`warn`); oylik va kredit bir haftaga tushgan (`warn`); tushum oxirgi 2 hafta o'rtachadan 20%+ past (`warn`); kategoriya xarajati o'tgan oyga nisbatan 30%+ oshgan (`info`); yangi `DataIssue` (`info`).
- `dedupe_key = f"{business}:{kind}:{date}"` — har 15 daqiqada takror yaratilmaydi; holat yaxshilansa avtomatik yopiladi.
- Matn: `light` model, faqat tool `display` qiymatlari bilan, "qaror + bitta ko'rsatma" uslubida; LLM ishlamasa shablon matn.
- **Kunlik maslahat (har kuni 08:00, Asia/Tashkent):** bosh sahifadagi qora banner + chatdagi "AI CFO · 08:00" xabari (`design/pages/Main.html`, `Chat.html`).
- Frontend: sahifa fokusga kelganda va har 60 soniyada `GET /api/alerts?since=` (WebSocket yo'q). Telegram — MVP'da yo'q.

### 5.9 O'rganish va xotira (`apps/knowledge`, pgvector)
- **Tuzatish → qoida:** chat yoki UI'dagi tuzatish ("Agro Go'shtga doim 15 kun kechiktirib to'laymiz") → `light` model structured output bilan `RuleCandidate` → foydalanuvchi "To'g'ri, eslab qol" bosadi → `BusinessRule` + `MemoryItem(kind=rule)`. Qoida **engine'ga** ta'sir qiladi (prognoz qayta hisoblanadi, kesh bekor qilinadi). Yaratishdan oldin pgvector bilan o'xshashlik tekshiruvi: cosine ≥ 0.9 bo'lsa "bu qoida allaqachon bor".
- **"AI sezdi":** tunda takrorlanuvchi to'lovlarni aniqlash (bir kontragent/kategoriya, har oy ±3 kun, summa ±15%, ≥ 3 marta) → `RuleCandidate(origin=pattern)` → "AI bilimi" sahifasida tasdiqlash kartasi.
- **Aniqlik:** tunda (03:00) o'tgan haftalik `ForecastSnapshot` haqiqiy natija bilan solishtiriladi → `ForecastAccuracy.mape`; `weekday_factors` EWMA (α = 0.3) bilan yangilanadi. "AI bilimi" sahifasidagi haftalik grafik shu jadvaldan.
- **Segment bilimi:** tunda `segment_key = kind:city:revenue_band` bo'yicha agregatsiya (median weekday factors, yanvar pasayishi %, oylik/tushum nisbati). **Faqat `n_businesses ≥ 5`** bo'lsa yoziladi; nomlar, summalar, tranzaksiyalar yo'q. Matnli xulosalar `MemoryItem(business=NULL, kind=segment_insight)`.
- **pgvector qoidalari:** `vector(768)`, HNSW `vector_cosine_ops`; har qidiruv **majburiy** `WHERE business_id = :current OR business_id IS NULL`. Tranzaksiya, balans va summalar vektorga **yozilmaydi** — ular faqat SQL va engine'da.

### 5.10 Amallar va tasdiqlash (`apps/actions`)
- AI faqat `proposed` yaratadi. `approved` faqat: UI tugmasi (`POST /api/actions/<id>/approve`) yoki Live'da foydalanuvchi "ha" degandan keyingi `confirm_plan`.
- `idempotency_key` — qayta urinishda dublikat yo'q.
- MVP'da "bajarish" = ilova ichidagi eslatma (`/api/reminders`, bosh sahifada va bildirishnomada ko'rinadi) va xarajat chegarasi. Real to'lov yo'q.
- Hammasi `AuditLog` da: kim, qachon, qaysi tool, qanday argument.

### 5.11 Scheduler (`manage.py run_scheduler`)
Oddiy asyncio sikl (kutubxonasiz yoki minimal): har 15 daqiqada `sync_all`, 08:00 da `daily_brief`, 03:00 da `nightly_learning` (aniqlik, pattern, segment). Har bir ish advisory lock bilan; xato bitta biznesda bo'lsa boshqalari davom etadi; strukturali log.

---

## 6. Kechikish talablari (byudjet) — o'lchanadi, taxmin qilinmaydi

| Yo'l | Maqsad (p50 / p95) |
|---|---|
| `/live` ochilgandan sessiya tayyor bo'lguncha | ≤ 1,0 s / ≤ 1,5 s |
| Foydalanuvchi gapini tugatgandan AI'ning birinchi ovozigacha (tool'siz) | ≤ 0,8 s / ≤ 1,5 s |
| Xuddi shu, bitta tool bilan | ≤ 1,4 s / ≤ 2,0 s |
| `POST /api/tools/*` server vaqti | ≤ 60 ms / ≤ 150 ms |
| Tool natijasidan kartaning ekranda chizilishigacha | ≤ 100 ms |
| Chat: yuborishdan `blocks` hodisasigacha | ≤ 1,2 s / ≤ 2,0 s |
| Chat: yuborishdan to'liq `answer` gacha | ≤ 2,5 s / ≤ 4,0 s |
| Chat chip (LLM'siz) | ≤ 300 ms |
| `GET /api/dashboard` (bitta so'rovda butun sahifa) | ≤ 100 ms / ≤ 200 ms |
| `simulate` (engine, bitta) | ≤ 5 ms |

Majburiy usullar:
- Ovoz yo'lida **ikkinchi LLM, embedding va qidiruv yo'q**; kontekst sessiya boshida yuklanadi.
- Dashboard/prognoz sahifalari oldindan hisoblangan `ForecastSnapshot` dan; har bir sahifa **bitta** API so'rovi bilan.
- DB: psycopg pool, kerakli indekslar, N+1 yo'q (test bilan tekshir: `django_assert_max_num_queries`).
- Brauzer: TanStack Query kesh, dashboard ma'lumotini chat/Live'ga o'tganda qayta ishlatish, route-level code splitting (Live sahifasi va Recharts alohida chunk), shriftlar `preload`.
- O'lchash: backend — har bir so'rovda `Server-Timing` (`db`, `engine`, `llm`, `embed`); frontend — Live uchun `speech_end → first_audio`, `tool_call → tool_response`, `tool_response → card_rendered`; chat uchun `send → blocks`, `send → answer`. Frontend hodisalarni to'plab `POST /api/telemetry` ga yuboradi → `LatencyEvent`.
- `make latency` (`manage.py latency_report`) — kanal va hodisa bo'yicha p50/p95 jadvali. Byudjetdan oshgan har bir yo'l uchun sabab va tuzatish `docs/LATENCY.md` da.

---

## 7. Frontend

- **Dizayn manbai:** avval `design/DESIGN.md` ni to'liq o'qi, keyin har bir sahifani `design/pages/*.html` dan **aynan** ko'chir: ranglar, o'lchamlar, bo'shliqlar, radiuslar, o'zbekcha matnlar. Tokenlarni `tailwind.config` ga va shadcn tema o'zgaruvchilariga kirit. O'zingdan yangi rang yoki o'lcham qo'shma. `design/screens/*.png` bo'lsa, ular bilan vizual solishtir.
- Route'lar: `/` (Main), `/chat`, `/live`, `/forecast`, `/calendar`, `/knowledge`, `/sources`, `/onboarding/connect`, `/login`.
- Komponentlar `DESIGN.md` dagi ro'yxat bo'yicha, bir marta yoziladi va qayta ishlatiladi; `UiBlockRenderer` bitta — chat ichida ham, Live o'ng panelida ham.
- Barcha raqamlar backend'dan. Komponentlarda demo raqam qattiq yozilmaydi.
- Holatlar: yuklanish (skeleton), bo'sh ("Jadvalingizni ulang"), `insufficient_data` ("Ishonchli prognoz uchun kamida 2 haftalik ma'lumot kerak"), xato (o'zbekcha, nima qilish kerakligi bilan).
- Mobil: kamida 390 px kenglikda buzilmasin (sidebar yuqoriga o'tadi, jadvallar gorizontal aylanadi). Har bir bosiladigan element ≥ 44 px. Klaviatura bilan ishlash, `aria-label`, kontrast ≥ 4.5:1. `prefers-reduced-motion` hurmat qilinadi.
- Auth: Django session (email + parol), `/login`. Biznes almashtirgich (sidebar pastida) — bir foydalanuvchi bir nechta biznesga ega bo'lishi mumkin.

---

## 8. Demo ma'lumotlari va seed

`python manage.py seed_demo`:
- foydalanuvchi `demo@demo.uz` (parol README'da), biznes **"Navro'z Kafe"** — `DESIGN.md` dagi raqamlar bilan aynan (8 oylik tarix: hafta kuni tushumlari ± kichik shovqin, lekin oxirgi 8 hafta o'rtachasi aynan 5.8…8.2 chiqsin; oltin testlar o'tsin);
- segment bilimi ishlashi uchun yana **5 ta** sintetik Toshkent kafesi (boshqa nomlar va raqamlar);
- 3 ta tasdiqlangan qoida va 1 ta "AI sezdi" kartasi (`design/pages/Knowledge.html` dagidek), 4 hafta `ForecastAccuracy` (14% → 11% → 8% → 6%);
- `seed_demo` OAuth'siz ishlaydi (Google ulanmasa ham demo to'liq ko'rsatiladi).
- `backend/fixtures/sheets/` — testlar uchun "chalkash" jadvallar (`FakeSheetsClient` orqali): header 3-qatorda, kirill sarlavhalar, aralash sana formatlari, "Kirim/Chiqim" alohida ustunlar, takror qatorlar, bo'sh summalar.

---

## 9. Ish tartibi va bosqichlar

**Boshlashdan oldin:** butun repo, `design/` va shu faylni o'qi, `docs/PLAN.md` da reja yoz (bosqichlar, fayllar, xavflar, ochiq savollar), **meni tasdiqlashimni kut**. Keyin bosqichma-bosqich ishla; har bosqich oxirida testlarni ishga tushir, nimani qilganingni va nima qolganini qisqa yoz, keyingisiga o'tishdan oldin to'xta. Repo ildizida `CLAUDE.md` yarat va yuritib bor (buyruqlar, konventsiyalar, qarorlar).

| # | Bosqich | Natija (qabul mezonlari) |
|---|---|---|
| M0 | Skelet | `make db && make dev` ishlaydi; `/api/health` → `{"ok":true,"app":APP_NAME}`; React sahifa Django orqali beriladi va `APP_NAME` ni ko'rsatadi; `check_ai` hamma modelni tasdiqlaydi; pgvector extension yoqilgan; `.env.example` faqat 8 ta o'zgaruvchi |
| M1 | Engine | 5.3 dagi **barcha oltin testlar** o'tadi; `simulate` benchmark < 5 ms; `uz_format` testlari o'tadi; engine Django'ni import qilmaydi (test bilan tekshir) |
| M2 | Ma'lumot + tenancy + dashboard | modellar, migratsiyalar, `seed_demo`; `GET /api/dashboard`, `/api/forecast`, `/api/calendar?month=`, `/api/simulate`; Main, Forecast (simulyator 3 preset bilan), Calendar sahifalari dizayndagidek va real API'dan; tenant izolyatsiyasi testlari |
| M3 | Tool'lar + chat | tool registry, `/api/tools/*`, SSE chat, raqam qo'riqchisi, chip tezkor yo'li; Chat sahifasi: "25 mln jihoz" savoliga dizayndagi `AnswerCard` (verdict, compare bars, 3 qadam, "Ha, shunday qilamiz" → `ActionPlan approved`) |
| M4 | Jonli ovoz | `/api/live/session`, Live sahifasi; o'zbekcha savol → tool chaqiruvi → kartalar o'ng panelda → o'zbekcha ovozli javob → "ha" → reja tasdiqlanadi; barge-in ishlaydi; qayta ulanish ishlaydi; kechikish o'lchovlari yoziladi |
| M5 | Google Sheets | OAuth, havola qo'shish, avtomatik header/mapping, tasdiqlash ekrani (Connect), normalizatsiya testlari (fixture'lar), scheduler sync har 15 daqiqada, Sources sahifasi; jadvalga yangi qator qo'shilsa ≤ 15 daqiqada prognoz yangilanadi |
| M6 | Proaktivlik | ogohlantirish qoidalari, dedupe, kunlik maslahat 08:00, bosh sahifa banneri va "Nima qilish kerak", qo'ng'iroqcha belgisi |
| M7 | O'rganish | tuzatish → `RuleCandidate` → qoida → prognoz o'zgaradi; pattern aniqlash; aniqlik grafigi; segment bilimi (n ≥ 5); pgvector xotira; Knowledge sahifasi |
| M8 | Tezlik + deploy | `make latency` jadvali 6-bo'lim byudjetiga mos (mos kelmasa — sabab va reja `docs/LATENCY.md` da); Dockerfile; Railway'da `web` + `scheduler` + `postgres`; README: lokal ishga tushirish, Google OAuth sozlash, deploy |

**Demo stsenariysi (M8 dan keyin 3 daqiqada qayta-qayta ishlashi kerak):** login → bosh sahifa (banner: "Pulingiz yetadi. Faqat 10-dekabrga ehtiyot bo'ling.") → Live: "25 million so'mga jihoz olsam, oylikka yetadimi?" → o'zbekcha ovozli javob + kartalar → "Ha" → reja tasdiqlandi → chatda yozma tuzatish → qoida saqlandi → prognoz yangilandi.

---

## 10. Taqiqlar va sifat

- `float` pul uchun, LLM arifmetikasi, LLM'ga boshqa biznes ma'lumoti, tool argumentida `business_id` — **taqiqlangan**.
- 2-bo'limdan tashqari kutubxona qo'shishdan oldin sababini `docs/PLAN.md` ga yoz va so'ra.
- Maxfiy qiymatlar (`GEMINI_API_KEY`, OAuth secret, refresh token) — logda, xato xabarida, frontend bundle'da, git'da **bo'lmasin**. `.env` `.gitignore` da.
- Kod: type hint'lar, `ruff` + `mypy` (backend), `eslint` + `tsc --noEmit` (frontend), testlar yashil bo'lmaguncha bosqich tugamaydi.
- Noaniq joyda taxmin qilib katta narsa qurma — `docs/PLAN.md` dagi "Ochiq savollar"ga yoz va so'ra.

---

**`GEMINI_API_KEY` va Google OAuth kalitlari `.env` faylida bor. Ularni faqat `os.environ` / settings orqali o'qi va hech qachon kodga, logga yoki commit'ga yozma.**

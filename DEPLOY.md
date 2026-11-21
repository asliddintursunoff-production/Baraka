# Deploy: GitHub → Railway (baza + backend + scheduler) va Vercel (frontend)

Hammasi GitHub'dan: `main` ga push qilinsa, Railway va Vercel o'zi qayta deploy qiladi. SSH yoki CLI kerak emas.

```
Brauzer ─► Vercel (frontend/, React SPA)
              │  /api/*, /app-config.js  ──rewrite──►  Railway "web"  (Dockerfile: Django API)
              │                                            │  private network
              │                                            ▼
              │                                        Railway "pgvector"  (Docker image pgvector/pgvector:pg16 + Volume)
              │                                            ▲
              └─ Live ovoz: brauzer → Gemini Live           Railway "scheduler" (xuddi shu repo, run_scheduler)
```

Railway'da **3 ta servis** bo'ladi, Vercel'da **1 ta project**. Redis yoki boshqa baza kerak emas.

---

## Servis 1: `pgvector` (baza, Docker image)

Railway'ning oddiy Postgres'ida `vector` kengaytmasi yo'q, shuning uchun bazani rasmiy pgvector image'idan ko'taramiz.

**Yaratish:** project → `+ New` → **Docker Image** → `pgvector/pgvector:pg16` → Deploy.

**Settings:**

| Sozlama | Qiymat |
|---|---|
| Service name | `pgvector` (pastdagi `${{pgvector.…}}` havolalar shu nomga bog'langan) |
| Volume | servis ustida o'ng tugma → **Attach Volume** → Mount path: `/var/lib/postgresql/data` |
| Networking | Public domain **kerak emas**. Baza faqat private network'da (`pgvector.railway.internal:5432`) |
| Restart policy | Always |

**Variables:**

| Nomi | Qiymat |
|---|---|
| `POSTGRES_USER` | `bizpilot` |
| `POSTGRES_PASSWORD` | kuchli parol, **faqat harf va raqam** (URL ichida ishlatiladi), masalan `python3 -c "import secrets;print(secrets.token_hex(24))"` |
| `POSTGRES_DB` | `bizpilot` |
| `PGDATA` | `/var/lib/postgresql/data/pgdata` (volume ildizida `lost+found` bor, shuning uchun ichki papka) |

`CREATE EXTENSION vector` ni birinchi migratsiya o'zi bajaradi.

---

## Servis 2: `web` (Django API, GitHub'dan)

**Yaratish:** `+ New` → **GitHub Repo** → `asliddintursunoff-production/Baraka`.

**Settings:**

| Sozlama | Qiymat |
|---|---|
| Service name | `web` |
| Source → Branch | `main` |
| Source → Root Directory | bo'sh (repo ildizi) |
| Config-as-code → Railway config file | `railway.json` (Builder: Dockerfile, Start: `/app/docker/start-web.sh`, Healthcheck: `/api/health`, timeout 120 s) |
| Watch Paths (ixtiyoriy) | `backend/**`, `frontend/**`, `docker/**`, `Dockerfile`, `railway.json`. Faqat hujjat o'zgarsa qayta deploy bo'lmaydi. |
| Networking | **Generate Domain** → Target port: `8000` → masalan `baraka-web.up.railway.app` |

Har deploy'da start skript `migrate` qiladi, `SEED_DEMO=1` bo'lsa demo ma'lumotni bir marta yaratadi, keyin gunicorn + uvicorn ishga tushadi.

**Variables:**

| Nomi | Qiymat |
|---|---|
| `APP_NAME` | `BizPilot AI` |
| `APP_URL` | foydalanuvchi ochadigan manzil: **Vercel domeni**, masalan `https://baraka.vercel.app` (oxirida `/` yo'q). Vercel tayyor bo'lguncha: `https://${{RAILWAY_PUBLIC_DOMAIN}}` |
| `DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | uzun tasodifiy satr: `python3 -c "import secrets;print(secrets.token_urlsafe(64))"`. **scheduler'da ham aynan shu** (Google token'lar shu kalit bilan shifrlanadi) |
| `DATABASE_URL` | `postgres://${{pgvector.POSTGRES_USER}}:${{pgvector.POSTGRES_PASSWORD}}@${{pgvector.RAILWAY_PRIVATE_DOMAIN}}:5432/${{pgvector.POSTGRES_DB}}` |
| `GEMINI_API_KEY` | Gemini kaliti (billing yoqilgan) |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth web client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_PICKER_API_KEY` | Google Picker API kaliti |
| `PORT` | `8000` (domen target port'i bilan bir xil) |
| `SEED_DEMO` | ixtiyoriy: `1` bo'lsa `demo@demo.uz / demo12345` va 6 ta demo kafe yaratiladi, faqat ular hali yo'q bo'lsa. Kerak bo'lmasa qo'shmang. |
| `WEB_CONCURRENCY` | ixtiyoriy, gunicorn worker soni (standart `2`) |

**Tekshirish:** `https://<web-domen>/api/health?deep=1` → `{"ok": true, "app": "...", "db": true}`

---

## Servis 3: `scheduler` (fon vazifalari, GitHub'dan)

Har 15 daqiqada Google Sheets sinxron va har kuni 08:00 xulosa (shablon, LLM chaqirmaydi). Ilova usiz ham ishlaydi, faqat avtomatik yangilash bo'lmaydi.

**Yaratish:** yana `+ New` → **GitHub Repo** → xuddi shu `Baraka`.

**Settings:**

| Sozlama | Qiymat |
|---|---|
| Service name | `scheduler` |
| Source → Branch | `main` |
| Config-as-code → Railway config file | **`railway.scheduler.json`** (Start: `python manage.py run_scheduler`, healthcheck yo'q). Buni o'zgartirmasangiz, scheduler ham web serverni ishga tushiradi. |
| Networking | domen **kerak emas** |
| Watch Paths (ixtiyoriy) | `backend/**`, `Dockerfile`, `railway.scheduler.json` |

**Variables:** `APP_NAME`, `APP_URL`, `DEBUG`, `DJANGO_SECRET_KEY` (web bilan bir xil), `DATABASE_URL` (web bilan bir xil formula), `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`. `GEMINI_API_KEY` va `GOOGLE_PICKER_API_KEY` kerak emas.

Qulay yo'l: bu qiymatlarni project → Settings → **Shared Variables** ga yozib, ikkala servisga ulang.

---

## Vercel: frontend

1. **Avval repoda** `frontend/vercel.json` ichidagi `YOUR-BACKEND.up.railway.app` ni `web` domeniga almashtiring (2 joy), commit va push qiling.
2. vercel.com → **Add New → Project** → `Baraka` → Import:

| Sozlama | Qiymat |
|---|---|
| Root Directory | **`frontend`** |
| Framework Preset | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Install Command | `npm ci` |
| Node.js Version | 22.x (Settings → General) |
| Environment Variables | **kerak emas**: nom va narxlar backend'dan `/app-config.js` orqali keladi |

3. Deploy → domen (masalan `https://baraka.vercel.app`) → Railway'da `APP_URL` ni shu domenga o'zgartiring (web va scheduler).

---

## Google Cloud Console (`APP_URL` = Vercel domeni)

- OAuth client → **Authorized JavaScript origins:** `https://baraka.vercel.app`
- **Authorized redirect URIs:** `https://baraka.vercel.app/api/integrations/google/callback`
- Picker API key → **HTTP referrers:** `https://baraka.vercel.app/*`
- Audience → **Test users:** sinovchilar Gmail'lari (Testing holatida)
- Lokal ishlash uchun `http://localhost:8000` yozuvlarini ham qoldiring.

---

## Tartib (birinchi marta)

1. Railway: `pgvector` (image + volume + 4 ta variable).
2. Railway: `web` (GitHub, variables, domen) → `/api/health?deep=1` tekshiring.
3. Railway: `scheduler` (GitHub, `railway.scheduler.json`).
4. Repoda `frontend/vercel.json` ga web domenini yozing → push.
5. Vercel project (Root `frontend`) → domen.
6. Railway `APP_URL` = Vercel domeni; Google Console'ni yangilang.

Keyin har `git push origin main` → Railway (web, scheduler) va Vercel avtomatik qayta deploy qiladi.

## Muammolar

| Belgi | Yechim |
|---|---|
| `web` loglarida `could not translate host name "pgvector.railway.internal"` | Baza servisining nomi `pgvector` emas. `DATABASE_URL` dagi `${{pgvector.…}}` ni haqiqiy servis nomiga moslang. |
| `password authentication failed` | Parolda maxsus belgi bor: faqat harf va raqamdan iborat parol qo'ying, so'ng `pgvector` volume'ini tozalab qayta yarating (parol faqat birinchi ishga tushishda yoziladi). |
| `400 Bad Request` | `APP_URL` noto'g'ri. `*.up.railway.app` avtomatik ruxsat etilgan. |
| `403 CSRF` login'da | `APP_URL` brauzerdagi manzil bilan aynan bir xil bo'lsin (`https://`, oxirida `/` yo'q) |
| Google `redirect_uri_mismatch` | Redirect URI = `APP_URL` + `/api/integrations/google/callback` |
| Healthcheck yiqiladi | `PORT=8000` va domen target port'i `8000` ekanini tekshiring. Loglarda migratsiya xatosi yo'qligini ko'ring. |
| Chat javobi oqim emas, birdaniga chiqadi | Vercel proksisi buferlayapti. Vercel'siz Railway domenini ishlating (`APP_URL` = Railway domeni): Docker image frontend'ni ham beradi. |

## Lokal (Docker)

```bash
cp .env.example .env        # to'ldiring; .env hech qachon git'ga tushmaydi
docker compose up --build   # db (pgvector) + web + scheduler → http://localhost:8000
```

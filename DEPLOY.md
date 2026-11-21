# Deploy qo'llanmasi: Railway (backend + baza) + Vercel (frontend)

## 1. Arxitektura

```
Brauzer ──► Vercel (React SPA, frontend/)
              │  /api/*  va  /app-config.js  ──rewrite──►  Railway "web" (Django API, Dockerfile)
              │                                               │
              │                                               ├─► Railway "Postgres + pgvector"
              │                                               └─► Google Gemini, Google OAuth/Drive/Sheets
              └─ Live ovoz: brauzer to'g'ridan-to'g'ri Gemini Live'ga (backend bergan vaqtinchalik token bilan)

Railway "scheduler" (xuddi shu Docker image): har 15 daqiqada Sheets sinxron, 08:00 xulosa
```

- **Frontend (Vercel):** faqat statik fayllar. API so'rovlari Vercel'ning `rewrites` orqali Railway'ga proksi qilinadi. Shuning uchun brauzer uchun hammasi **bitta domen**: cookie, CSRF va Google OAuth qo'shimcha sozlamasiz ishlaydi, CORS kerak emas.
- **Backend (Railway):** ildizdagi `Dockerfile`. U React build'ni ham o'z ichiga oladi, shuning uchun Railway domeni o'zi ham to'liq ilova sifatida ishlaydi (Vercel'siz zaxira variant, 7-bo'limga qarang).
- **Bazalar:** faqat bitta **PostgreSQL 16 + pgvector**. Redis, Celery, alohida vektor bazasi **kerak emas**: navbatlar va kesh Postgres va jarayon ichida.

## 2. Railway: qaysi servislar kerak

| Servis | Nima | Qanday yaratiladi |
|---|---|---|
| **Postgres (pgvector)** | Yagona baza | `+ New → Template` → **"pgvector"** deb qidiring → Deploy. Oddiy "PostgreSQL" ham ishlaydi, faqat unda `vector` kengaytmasi bo'lishi shart (birinchi migratsiya `CREATE EXTENSION vector` qiladi). |
| **web** | Django API (+ SPA) | `+ New → GitHub Repo → Baraka`. Config-as-code: `railway.json` |
| **scheduler** | Fon vazifalari (LLM chaqirmaydi) | Yana `+ New → GitHub Repo → Baraka`. Config-as-code: `railway.scheduler.json` |

## 3. Railway: qadamma-qadam

1. **Project:** railway.com → *New Project* → *Deploy from GitHub repo* → `asliddintursunoff-production/Baraka` → *main*.
   Bu birinchi servis **web** bo'ladi. Settings → *Service name*: `web`.
2. **Baza:** project ichida `+ New` → *Template* → **pgvector** → *Deploy*. Nomi masalan `Postgres`.
3. **web sozlamalari** (Settings):
   - *Source → Root Directory*: bo'sh qoldiring (repo ildizi).
   - *Config-as-code → Railway Config File*: `railway.json`. Builder Dockerfile, start `/app/docker/start-web.sh`, health check `/api/health`.
   - *Networking → Generate Domain*, masalan `baraka-web.up.railway.app`. Port: `8000`; Railway `PORT` beradi, skript uni ishlatadi.
   - Start skript har deploy'da `migrate` qiladi, keyin gunicorn + uvicorn ishga tushadi.
4. **Variables:** *Shared Variables* (project → Settings → Shared Variables) ga yozing va ikkala servisga ulang:

   | O'zgaruvchi | Qiymat |
   |---|---|
   | `APP_NAME` | `BizPilot AI` (yoki istalgan nom) |
   | `APP_URL` | foydalanuvchi ochadigan manzil: **Vercel domeni**, masalan `https://baraka.vercel.app` (oxirida `/` yo'q). Vercel hali bo'lmasa, vaqtincha Railway domeni. |
   | `DEBUG` | `false` |
   | `DJANGO_SECRET_KEY` | uzun tasodifiy satr (`python -c "import secrets;print(secrets.token_urlsafe(64))"`). Ikkala servisda **bir xil**: refresh token'lar shu kalit bilan shifrlanadi. |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (baza servisiga havola; nomi boshqacha bo'lsa o'shani yozing) |
   | `GEMINI_API_KEY` | Gemini kaliti (billing yoqilgan) |
   | `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth Web client ID |
   | `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
   | `GOOGLE_PICKER_API_KEY` | Picker API kaliti |

   `DEBUG=false` = **demo profil**: chat `gemini-3.8-flash` va zaxira modellar bilan ishlaydi. AI xarajati `AiUsage` jadvalida hisoblanadi: limit kuniga $0.50, jami $4.00.
5. **scheduler servisi:** `+ New → GitHub Repo → Baraka` → Settings:
   - *Service name*: `scheduler`.
   - *Config-as-code*: `railway.scheduler.json` (start `python manage.py run_scheduler`, HTTP health check yo'q).
   - Domen kerak emas. Variables: o'sha shared variables.
6. **Deploy** tugagach tekshiring: `https://<web-domen>/api/health?deep=1` → `{"ok": true, "app": "...", "db": true}`.
7. **Demo ma'lumot (bir marta, ixtiyoriy):** Railway CLI bilan:
   ```bash
   npm i -g @railway/cli
   railway login
   railway link            # Baraka project'ni tanlang
   railway ssh --service web
   python manage.py seed_demo --reset
   ```
   Bu `demo@demo.uz / demo12345` hisobini va 6 ta demo kafe statistikasini yaratadi. Yangi ro'yxatdan o'tgan foydalanuvchi "Demo kafe bilan sinab ko'rish" tugmasi bilan o'zining alohida demo biznesini oladi, bunga seed shart emas.

## 4. Vercel: frontend

1. **Avval** `frontend/vercel.json` ichidagi `YOUR-BACKEND.up.railway.app` ni 3-qadamdagi Railway web domeniga almashtiring (2 joyda), commit qiling va push qiling:
   ```json
   { "source": "/api/:path*", "destination": "https://baraka-web.up.railway.app/api/:path*" }
   ```
2. vercel.com → *Add New… → Project* → `Baraka` repo → *Import*:
   - **Root Directory: `frontend`** (muhim)
   - Framework Preset: *Vite* (o'zi aniqlaydi)
   - Build Command: `npm run build`, Output Directory: `dist`
   - Environment variables: **kerak emas**. Ilova nomi va narxlar backend'dan `/app-config.js` orqali keladi.
3. *Deploy*. Domen, masalan `https://baraka.vercel.app`.
4. Railway'da `APP_URL` ni shu Vercel domeniga o'zgartiring (shared variable) → ikkala servis qayta deploy bo'ladi.

## 5. Google Cloud (OAuth + Picker)

Console → *Google Auth Platform* va *Credentials*:
- **OAuth client → Authorized JavaScript origins:** `https://baraka.vercel.app`
- **Authorized redirect URIs:** `https://baraka.vercel.app/api/integrations/google/callback`. Har doim `APP_URL` + `/api/integrations/google/callback`, harfma-harf bir xil.
- **Picker API key → HTTP referrers:** `https://baraka.vercel.app/*`
- **Audience → Test users:** sinovchilarning Gmail'lari (ilova *Testing* holatida bo'lsa).
- Local ishlash uchun `http://localhost:8000` yozuvlarini ham qoldiring.

## 6. Tekshirish ro'yxati

- [ ] `https://<web-domen>/api/health?deep=1` → `db: true`
- [ ] `https://<vercel-domen>/` → Landing ochiladi, `/pricing` ishlaydi
- [ ] Ro'yxatdan o'tish → Biznes profili → Jadval ulash bosqichi
- [ ] "Demo kafe bilan sinab ko'rish" → `/dashboard` ochiladi, chap pastda "Demo" belgisi
- [ ] "Google bilan ulash" → Google kirish → Picker → jadval → ustunlar → "Birinchi tahlil" → dashboard
- [ ] AI CFO chat: "25 mln jihoz olsam?" → kartalar va javob
- [ ] `/live`: mikrofon ruxsati → ovozli javob

## 7. Muammolar va yechimlar

| Belgi | Sabab | Yechim |
|---|---|---|
| `400 Bad Request` (DisallowedHost) | Domen ruxsat etilmagan | `APP_URL` to'g'ri ekanini tekshiring. `*.up.railway.app` avtomatik ruxsat etilgan. O'z domeningiz bo'lsa, `APP_URL` shu domen bo'lsin. |
| `403 CSRF` login'da | `APP_URL` brauzerdagi manzil bilan bir xil emas | `APP_URL` = aynan foydalanuvchi ochadigan domen (`https://`, oxirida `/` yo'q) |
| Google: `redirect_uri_mismatch` | Redirect URI Console'da boshqacha | 5-bo'limdagi URI'ni aynan `APP_URL` bilan yozing |
| Migratsiya xatosi: `extension "vector" is not available` | Baza pgvector'siz | Bazani **pgvector** template'dan yarating va `DATABASE_URL` ni yangilang |
| Chat javobi oxirida bir martada chiqadi (stream yo'q) | Proksi SSE'ni buferlaydi | Zaxira variant: Vercel'siz, Railway domenini to'g'ridan-to'g'ri ishlating (`APP_URL` = Railway domeni, Google sozlamalarida ham). Docker image SPA'ni ham beradi. |
| `AI hozir band` | Gemini 429 / kvota | Billing yoqilganini tekshiring. Limit tugasa chat shablon javob beradi, ovoz "Bugungi ovoz limiti tugadi" deydi. |
| Live ovoz ulanmaydi | Mikrofon ruxsati yoki HTTPS | Faqat HTTPS'da ishlaydi (Vercel/Railway HTTPS beradi) |

## 8. Lokal ishga tushirish (Docker)

```bash
cp .env.example .env          # qiymatlarni to'ldiring (.env hech qachon git'ga tushmaydi)
docker compose up --build     # db + web + scheduler → http://localhost:8000
# yoki: make up / make down
docker compose exec web python manage.py seed_demo --reset   # demo ma'lumot (ixtiyoriy)
```
Hot reload bilan ishlash: `make install && make db && make dev` → http://localhost:5173.

## 9. Xavfsizlik

- `.env` `.gitignore` da. Barcha kalitlar faqat Railway Variables'da.
- GitHub token, Gemini va OAuth kalitlarini chat, issue yoki commit'ga yozmang. Tasodifan ko'rinib qolsa, darhol bekor qilib yangisini yarating.
- Google refresh token'lar bazada `DJANGO_SECRET_KEY` dan olingan kalit bilan shifrlangan. Shu kalitni almashtirsangiz, foydalanuvchilar Google'ni qayta ulashi kerak bo'ladi.

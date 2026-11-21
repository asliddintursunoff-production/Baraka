# Deploy: GitHub → Railway (baza + backend) va Vercel (frontend)

`main` ga push qilinsa, Railway va Vercel o'zi qayta deploy qiladi. SSH, CLI yoki config fayl kerak emas.

| Qayerda | Servis | Repodan qaysi papka | Nima |
|---|---|---|---|
| Railway | `pgvector` | — (Docker image) | PostgreSQL 16 + pgvector |
| Railway | `web` | `backend` | Django API (`backend/Dockerfile`) |
| Railway | `scheduler` | `backend` | fon vazifalari (ixtiyoriy) |
| Vercel | project | `frontend` | React sayt |

---

## 1. `pgvector`: baza

1. Railway project → **+ New** → **Docker Image** → `pgvector/pgvector:pg16` → Deploy.
2. Servis nomi: **`pgvector`** (Settings → Service name).
3. Servis ustida o'ng tugma → **Attach Volume** → Mount path: `/var/lib/postgresql/data`.
4. **Variables:**
   ```
   POSTGRES_USER=bizpilot
   POSTGRES_PASSWORD=<faqat harf va raqam, masalan: python3 -c "import secrets;print(secrets.token_hex(24))">
   POSTGRES_DB=bizpilot
   PGDATA=/var/lib/postgresql/data/pgdata
   ```
Domen kerak emas.

## 2. `web`: backend

1. **+ New** → **GitHub Repo** → `asliddintursunoff-production/Baraka`.
2. Settings:
   - **Service name:** `web`
   - **Root Directory:** `backend`. Shu yetarli: Railway `backend/Dockerfile` ni o'zi topadi, start buyrug'i Dockerfile ichida (migrate → server).
   - **Branch:** `main`
3. **Variables** (Raw Editor ga joylang):
   ```
   APP_NAME=BizPilot AI
   APP_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}
   DEBUG=false
   PORT=8000
   DJANGO_SECRET_KEY=<python3 -c "import secrets;print(secrets.token_urlsafe(64))">
   DATABASE_URL=postgres://${{pgvector.POSTGRES_USER}}:${{pgvector.POSTGRES_PASSWORD}}@${{pgvector.RAILWAY_PRIVATE_DOMAIN}}:5432/${{pgvector.POSTGRES_DB}}
   GEMINI_API_KEY=<kalit>
   GOOGLE_OAUTH_CLIENT_ID=<client id>
   GOOGLE_OAUTH_CLIENT_SECRET=<secret>
   GOOGLE_PICKER_API_KEY=<picker kaliti>
   SEED_DEMO=1
   ```
   `SEED_DEMO=1` = `demo@demo.uz / demo12345` demo hisobi (faqat birinchi marta yaratiladi). Kerak bo'lmasa olib tashlang.
4. Settings → Networking → **Generate Domain** → Port: `8000`. Masalan `web-production-1234.up.railway.app`.
5. (ixtiyoriy) Settings → Deploy → **Healthcheck Path:** `/api/health`
6. **Tekshirish:** brauzerda `https://<web-domen>/api/health?deep=1` → `{"ok": true, ..., "db": true}`

Vercel tayyor bo'lgach, `APP_URL` ni Vercel domeniga almashtirasiz (4-bo'lim).

## 3. `scheduler`: fon vazifalari (ixtiyoriy)

Har 15 daqiqada Google Sheets sinxron va 08:00 xulosa. Usiz ham ilova ishlaydi, "Hozir yangilash" tugmasi qo'lda sinxron qiladi.

1. **+ New** → **GitHub Repo** → xuddi shu `Baraka`.
2. Settings:
   - **Service name:** `scheduler`
   - **Root Directory:** `backend`
   - **Custom Start Command** (Settings → Deploy): `python manage.py run_scheduler`
   - Domen kerak emas.
3. **Variables:** web'dagi bilan bir xil: `APP_NAME`, `APP_URL`, `DEBUG`, `DJANGO_SECRET_KEY` (aynan bir xil!), `DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`.

## 4. Vercel: frontend

1. Repoda `frontend/vercel.json` ichidagi `YOUR-BACKEND.up.railway.app` ni web domeniga almashtiring (2 joy) va push qiling.
2. vercel.com → **Add New → Project** → `Baraka` → Import:
   - **Root Directory:** `frontend`
   - Framework: Vite, Build: `npm run build`, Output: `dist` (o'zi aniqlaydi)
   - Environment variables: kerak emas
3. Deploy → domen (masalan `https://baraka.vercel.app`).
4. Railway'da `web` va `scheduler` dagi `APP_URL` ni shu domenga o'zgartiring: `APP_URL=https://baraka.vercel.app`

## 5. Google Cloud Console

`APP_URL` = Vercel domeni bo'lsa:
- OAuth client → Authorized JavaScript origins: `https://baraka.vercel.app`
- Authorized redirect URIs: `https://baraka.vercel.app/api/integrations/google/callback`
- Picker API key → HTTP referrers: `https://baraka.vercel.app/*`
- Audience → Test users: sinovchilar Gmail'lari

## Muammolar

| Belgi | Yechim |
|---|---|
| Loglarda `could not translate host name "pgvector.railway.internal"` | Baza servisi nomi aynan `pgvector` emas. Nomini o'zgartiring yoki `DATABASE_URL` dagi `pgvector` so'zini haqiqiy nomga almashtiring. |
| `password authentication failed` | Parolda maxsus belgi bor. Faqat harf va raqam qo'ying, `pgvector` volume'ini o'chirib qayta yarating. |
| Domen ochilmaydi / healthcheck yiqiladi | `PORT=8000` va domen porti `8000` ekanini tekshiring. Deploy loglarida xato yo'qligini ko'ring. |
| `403 CSRF` login'da | `APP_URL` brauzerdagi manzil bilan aynan bir xil (`https://`, oxirida `/` yo'q). |
| Google `redirect_uri_mismatch` | Redirect URI = `APP_URL` + `/api/integrations/google/callback` |
| Railway domeni "API ishlayapti" deydi | To'g'ri: backend faqat API, sayt Vercel'da. |
| Chat javobi oqim emas, birdaniga chiqadi | Vercel proksisi buferlayapti. Zaxira: ildizdagi `Dockerfile` (frontend + backend birga) bilan bitta Railway servisi, Root Directory bo'sh. |

## Lokal (Docker)

```bash
cp .env.example .env        # to'ldiring; .env hech qachon git'ga tushmaydi
docker compose up --build   # db (pgvector) + web + scheduler → http://localhost:8000
```

# Deploy: hammasi Railway'da (GitHub'dan)

`main` ga push qilinsa, Railway o'zi qayta deploy qiladi. SSH, CLI yoki config fayl kerak emas.

| Servis | Manba | Nima |
|---|---|---|
| `pgvector` | Docker image `pgvector/pgvector:pg16` | baza (PostgreSQL 16 + pgvector) |
| `web` | GitHub `Baraka`, Root Directory **bo'sh** (ildizdagi `Dockerfile`) | sayt (React) + API (Django) **bitta domenda** |
| `scheduler` | GitHub `Baraka`, Root Directory `backend` | fon vazifalari (ixtiyoriy) |

---

## 1. `pgvector`: baza

1. Railway project → **+ New** → **Docker Image** → `pgvector/pgvector:pg16` → Deploy.
2. Servis nomi: **`pgvector`**.
3. Servis ustida o'ng tugma → **Attach Volume** → Mount path: `/var/lib/postgresql/data`.
4. **Variables:**
   ```
   POSTGRES_USER=bizpilot
   POSTGRES_PASSWORD=<faqat harf va raqam: python3 -c "import secrets;print(secrets.token_hex(24))">
   POSTGRES_DB=bizpilot
   PGDATA=/var/lib/postgresql/data/pgdata
   ```
Domen kerak emas.

## 2. `web`: sayt + API

1. **+ New** → **GitHub Repo** → `asliddintursunoff-production/Baraka`.
2. Settings:
   - **Service name:** `web`
   - **Root Directory:** **bo'sh qoldiring**. Ildizdagi `Dockerfile` frontendni build qiladi va Django bilan birga ishga tushiradi; start: migrate → server.
   - **Branch:** `main`
   - (ixtiyoriy) Deploy → **Healthcheck Path:** `/api/health`
3. **Variables** (Raw Editor):
   ```
   APP_NAME=Baraka
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
   `SEED_DEMO=1` = `demo@demo.uz / demo12345` demo hisobi (faqat birinchi marta yaratiladi).
4. Settings → Networking → **Generate Domain** → Port: `8000`. Masalan `web-production-1234.up.railway.app`.
5. **Tekshirish:**
   - `https://<domen>/api/health?deep=1` → `{"ok": true, ..., "db": true}`
   - `https://<domen>/` → bosh sahifa (Landing), `/login` → kirish

Build birinchi marta 5–10 daqiqa oladi (npm + pip).

## 3. `scheduler`: fon vazifalari (ixtiyoriy)

Har 15 daqiqada Google Sheets sinxron va 08:00 xulosa. Usiz ham ilova ishlaydi, "Hozir yangilash" tugmasi qo'lda sinxron qiladi.

1. **+ New** → **GitHub Repo** → xuddi shu `Baraka`.
2. Settings:
   - **Service name:** `scheduler`
   - **Root Directory:** `backend` (yengil image, frontend'siz)
   - Deploy → **Custom Start Command:** `python manage.py run_scheduler`
   - Domen kerak emas.
3. **Variables:**
   ```
   APP_NAME=Baraka
   APP_URL=https://${{web.RAILWAY_PUBLIC_DOMAIN}}
   DEBUG=false
   DJANGO_SECRET_KEY=<web'dagi bilan AYNAN bir xil>
   DATABASE_URL=postgres://${{pgvector.POSTGRES_USER}}:${{pgvector.POSTGRES_PASSWORD}}@${{pgvector.RAILWAY_PRIVATE_DOMAIN}}:5432/${{pgvector.POSTGRES_DB}}
   GOOGLE_OAUTH_CLIENT_ID=<client id>
   GOOGLE_OAUTH_CLIENT_SECRET=<secret>
   ```

## 4. Google Cloud Console

`<domen>` = web domeni (masalan `web-production-1234.up.railway.app`):
- OAuth client → **Authorized JavaScript origins:** `https://<domen>`
- **Authorized redirect URIs:** `https://<domen>/api/integrations/google/callback`
- Picker API key → **HTTP referrers:** `https://<domen>/*`
- Audience → **Test users:** sinovchilar Gmail'lari

## Muammolar

| Belgi | Yechim |
|---|---|
| Loglarda `could not translate host name "pgvector.railway.internal"` | Baza servisi nomi aynan `pgvector` emas. Nomini o'zgartiring yoki `DATABASE_URL` dagi `pgvector` so'zini haqiqiy nomga almashtiring. |
| `password authentication failed` | Parolda maxsus belgi bor. Faqat harf va raqam qo'ying, `pgvector` volume'ini o'chirib qayta yarating (parol faqat birinchi ishga tushishda yoziladi). |
| Domen ochilmaydi / healthcheck yiqiladi | `PORT=8000` va domen porti `8000` ekanini tekshiring. Deploy loglarini ko'ring. |
| Domen "API ishlayapti" deydi | Root Directory `backend` bo'lib qolgan. **Bo'sh** qiling, shunda ildizdagi `Dockerfile` (sayt + API) ishlatiladi. |
| `403 CSRF` login'da | `APP_URL` brauzerdagi manzil bilan aynan bir xil bo'lsin. `https://${{RAILWAY_PUBLIC_DOMAIN}}` shuni avtomatik beradi. |
| Google `redirect_uri_mismatch` | Redirect URI = `https://<domen>/api/integrations/google/callback` |
| Build'da `npm` yoki `pip` timeout | Railway'da **Redeploy** ni bosing (tarmoq vaqtinchalik). |

## Keyinchalik o'z domeningiz (ixtiyoriy)

`web` → Settings → Networking → **Custom Domain**. Keyin `APP_URL` ni shu domenga o'zgartiring va Google Console'dagi 3 ta manzilni yangilang.

## Lokal (Docker)

```bash
cp .env.example .env        # to'ldiring; .env hech qachon git'ga tushmaydi
docker compose up --build   # db (pgvector) + web + scheduler → http://localhost:8000
```

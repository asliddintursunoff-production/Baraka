# Deploy: hammasi Railway'da (GitHub'dan)

`main` ga push qilinsa, Railway o'zi qayta deploy qiladi.

| Servis | Manba | Nima |
|---|---|---|
| `pgvector` | Docker image `pgvector/pgvector:pg16` | baza |
| `web` | GitHub `Baraka`, Root Directory `backend` | API (Django) |
| `frontend` | GitHub `Baraka`, Root Directory `frontend` | sayt (React + Caddy). `/api` ni `web` ga proksi qiladi |
| `scheduler` | GitHub `Baraka`, Root Directory `backend` | fon vazifalari (ixtiyoriy) |

---

## 1. `pgvector`: baza

1. Railway project → **+ New** → **Docker Image** → `pgvector/pgvector:pg16` → Deploy.
2. Servis nomi: **`pgvector`**.
3. Servis ustida o'ng tugma → **Attach Volume** → Mount path: `/var/lib/postgresql/data`.
4. **Variables:**
   ```
   POSTGRES_USER=bizpilot
   POSTGRES_PASSWORD=<faqat harf va raqam>
   POSTGRES_DB=bizpilot
   PGDATA=/var/lib/postgresql/data/pgdata
   ```

## 2. `web`: backend (API)

1. **+ New** → **GitHub Repo** → `Baraka` → Settings → **Root Directory: `backend`**.
2. **Variables:**
   ```
   APP_NAME=Baraka
   APP_URL=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
   DEBUG=false
   PORT=8000
   DJANGO_SECRET_KEY=<uzun tasodifiy satr>
   DATABASE_URL=postgres://${{pgvector.POSTGRES_USER}}:${{pgvector.POSTGRES_PASSWORD}}@${{pgvector.RAILWAY_PRIVATE_DOMAIN}}:5432/${{pgvector.POSTGRES_DB}}
   GEMINI_API_KEY=<kalit>
   GOOGLE_OAUTH_CLIENT_ID=<client id>
   GOOGLE_OAUTH_CLIENT_SECRET=<secret>
   GOOGLE_PICKER_API_KEY=<picker kaliti>
   SEED_DEMO=1
   ```
   `APP_URL` = **frontend** domeni, chunki foydalanuvchi saytni o'sha domenda ochadi (login/CSRF va Google OAuth shunga bog'liq).
3. Networking → **Generate Domain** → Port `8000`.
4. Tekshirish: `https://<web-domen>/api/health?deep=1` → `"db": true`

## 2b. `frontend`: sayt

1. **+ New** → **GitHub Repo** → xuddi shu `Baraka`.
2. Settings:
   - **Service name:** `frontend`
   - **Root Directory:** `frontend`. Railway `frontend/Dockerfile` ni o'zi topadi: React build + Caddy.
   - **Branch:** `main`
3. **Variables:**
   ```
   BACKEND_URL=https://${{web.RAILWAY_PUBLIC_DOMAIN}}
   PORT=8080
   ```
4. Networking → **Generate Domain** → Port `8080`. Masalan `frontend-production-5678.up.railway.app`.
5. Tekshirish:
   - `https://<frontend-domen>/` → bosh sahifa
   - `https://<frontend-domen>/api/health?deep=1` → `"db": true` (proksi ishlayapti)
   - `/login` → `demo@demo.uz / demo12345` (`SEED_DEMO=1` bo'lsa)

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
   APP_URL=https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}
   DEBUG=false
   DJANGO_SECRET_KEY=<web'dagi bilan AYNAN bir xil>
   DATABASE_URL=postgres://${{pgvector.POSTGRES_USER}}:${{pgvector.POSTGRES_PASSWORD}}@${{pgvector.RAILWAY_PRIVATE_DOMAIN}}:5432/${{pgvector.POSTGRES_DB}}
   GOOGLE_OAUTH_CLIENT_ID=<client id>
   GOOGLE_OAUTH_CLIENT_SECRET=<secret>
   ```

## 4. Google Cloud Console

`<domen>` = **frontend** domeni (masalan `frontend-production-5678.up.railway.app`):
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
| Frontend'da `/api/...` 502 beradi | `frontend` dagi `BACKEND_URL` = `https://<web-domen>` (https bilan, oxirida `/` yo'q) ekanini tekshiring. |
| `web` domeni "API ishlayapti" deydi | To'g'ri: saytni **frontend** domenida oching. |
| `403 CSRF` login'da | `web` dagi `APP_URL` = frontend domeni bo'lsin (`https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}`). |
| Google `redirect_uri_mismatch` | Redirect URI = `https://<domen>/api/integrations/google/callback` |
| Build'da `npm` yoki `pip` timeout | Railway'da **Redeploy** ni bosing (tarmoq vaqtinchalik). |

## Keyinchalik o'z domeningiz (ixtiyoriy)

`web` → Settings → Networking → **Custom Domain**. Keyin `APP_URL` ni shu domenga o'zgartiring va Google Console'dagi 3 ta manzilni yangilang.

## Lokal (Docker)

```bash
cp .env.example .env        # to'ldiring; .env hech qachon git'ga tushmaydi
docker compose up --build   # db (pgvector) + web + scheduler → http://localhost:8000
```

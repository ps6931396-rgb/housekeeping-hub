# Setup Guide — Housekeeping Hub PRO

## 1. Requirements
- Python 3.9 or later
- pip

## 2. Local setup

```bash
# 1. Extract the project and enter the folder
cd HousekeepingHubPro

# 2. Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env      # Windows: copy .env.example .env
# then edit .env with your own SECRET_KEY / JWT_SECRET / admin credentials

# 5. Run the app
python app.py
```

Open **http://127.0.0.1:5000**. On first run, `app.py` calls `models.setup_database()`,
which:
- creates all tables if they don't exist,
- seeds 3 categories and 5 default services,
- seeds a default admin account (from `.env` or the built-in fallback),
- seeds default site settings (name, contact email/phone, currency, address).

## 3. Environment variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_DEBUG` | `true` | Flask debug/auto-reload mode |
| `PORT` | `5000` | Port for `python app.py` / Gunicorn |
| `SECRET_KEY` | dev fallback | Signs session cookies — **change in production** |
| `JWT_SECRET` | dev fallback | Signs API JWTs — **change in production, different from SECRET_KEY** |
| `JWT_EXP_MINUTES` | `60` | API token lifetime |
| `ADMIN_EMAIL` | `admin@housekeepinghub.com` | Seeded admin login (only used on first DB creation) |
| `ADMIN_PASSWORD` | `admin123` | Seeded admin password (only used on first DB creation) |
| `DATABASE_URL` | *(blank → SQLite)* | PostgreSQL connection string for persistent storage (see §8) |
| `CLOUDINARY_URL` | *(blank → local disk)* | Cloudinary connection string for persistent image uploads (see §8) |

> Changing `ADMIN_EMAIL`/`ADMIN_PASSWORD` after the database already exists does
> **not** change the existing admin account — update it from **Admin → Settings**
> instead, or delete `database/housekeeping.db` to reseed from scratch (this also
> wipes all data).

## 4. Resetting the database
Delete `database/housekeeping.db` and restart the app — it will be recreated and
reseeded automatically.

## 5. File uploads
Admin-uploaded service images are saved to `static/uploads/services/` with a random
UUID filename. Allowed extensions: `png, jpg, jpeg, webp, gif`. Max size: 5 MB
(`MAX_CONTENT_LENGTH` in `config.py`).

## 6. Running tests / smoke-checking routes
There's no separate test suite bundled; the fastest smoke check is:
```bash
python app.py
# then in another terminal:
curl -I http://127.0.0.1:5000/
curl -I http://127.0.0.1:5000/services
curl -I http://127.0.0.1:5000/admin/login
```
All should return `200`.

## 7. Production deployment

### Option A — Gunicorn on any VM
```bash
pip install -r requirements.txt
export SECRET_KEY=... JWT_SECRET=... ADMIN_EMAIL=... ADMIN_PASSWORD=...
gunicorn wsgi:app --workers 3 --bind 0.0.0.0:8000
```
Put Nginx or another reverse proxy in front for TLS termination and static file
caching.

### Option B — Platforms with a Procfile (Heroku-style / Render)
The included `Procfile` runs:
```
web: gunicorn wsgi:app --workers 3 --bind 0.0.0.0:$PORT
```
Set the environment variables from Section 3 in the platform's dashboard.

### Production checklist
- [ ] Set strong, unique `SECRET_KEY` and `JWT_SECRET`
- [ ] Set a real `ADMIN_EMAIL` / `ADMIN_PASSWORD` before first run, or change the
      password immediately after first login
- [ ] Set `FLASK_DEBUG=false`
- [ ] Serve behind HTTPS (session cookies should be marked `Secure` — add
      `SESSION_COOKIE_SECURE = True` to `config.py` once TLS is in place)
- [ ] Wire up a real email provider for password reset / verification links
      (currently shown on-screen in "demo mode" — see README §7)
- [ ] Set `DATABASE_URL` and `CLOUDINARY_URL` for persistent storage on hosts with
      ephemeral disks (Render free tier, etc.) — see §8 below
- [ ] Back up your database regularly (Neon/managed Postgres has its own backups;
      for local SQLite, back up `database/housekeeping.db`)

## 8. Persistent storage walkthrough — Neon (database) + Cloudinary (images)

Use this if you're deploying to a host with an ephemeral disk (e.g. Render free
tier) and your database/uploaded photos keep disappearing after the app sleeps
or redeploys.

### 8.1 Neon — free PostgreSQL database

1. Go to [neon.tech](https://neon.tech) and sign up (free).
2. Click **New Project**. Give it any name, pick a region close to your Render
   region, and create it.
3. On the project dashboard, find the **Connection string** box. Copy the string
   that looks like:
   ```
   postgresql://<user>:<password>@<host>.neon.tech/<database>?sslmode=require
   ```
4. In Render → your service → **Environment** tab → **Add Environment Variable**:
   - Key: `DATABASE_URL`
   - Value: the connection string you copied
5. Save and let Render redeploy. On the next startup, `models.setup_database()`
   detects `DATABASE_URL`, creates all tables in Neon, and seeds default
   categories/services/admin/settings automatically — no manual SQL needed.

### 8.2 Cloudinary — free image hosting for uploaded service photos

1. Go to [cloudinary.com](https://cloudinary.com) and sign up (free tier).
2. On the Cloudinary **Dashboard** (first page after login), find the box labeled
   **API Environment variable**. It looks like:
   ```
   cloudinary://123456789012345:AbCdEfGhIjKlMnOpQrStUvWxYz@your-cloud-name
   ```
   Click the copy icon next to it.
3. In Render → your service → **Environment** tab → **Add Environment Variable**:
   - Key: `CLOUDINARY_URL`
   - Value: the string you copied
4. Save and redeploy. From now on, every image an admin uploads via **Admin →
   Services → Add/Edit Service** is stored on Cloudinary and referenced by a
   permanent `https://res.cloudinary.com/...` URL saved in the database — it
   will keep working even if Render's disk is wiped.

### 8.3 Verifying it worked
- After redeploying with both variables set, log into `/admin`, add a new
  service with a photo, then manually restart the Render service (Render
  dashboard → **Manual Deploy** → **Deploy latest commit**, or just wait for it
  to sleep/wake on the free tier).
- Reload the site: the service, its photo, and any settings changes (site name,
  support email/phone, etc.) should still be there.
- If they still disappear, double-check both environment variables are saved
  under the correct service in Render and that you redeployed after adding them.

### 8.4 What if I only set one of the two?
They're independent:
- `DATABASE_URL` only → data (users, bookings, settings) persists, but uploaded
  images still go to local disk and can still disappear.
- `CLOUDINARY_URL` only → uploaded images persist, but the database itself is
  still local SQLite and can still be wiped (default services/admin will just
  reseed on next start, but real bookings/users would be lost).

For full persistence, set **both**.

## 9. Adding a new service category, service, or admin manually (without the UI)
Not necessary — everything is manageable from the Admin Panel (`/admin/categories`,
`/admin/services`). Direct SQLite/Postgres edits are only needed for advanced/bulk
operations.

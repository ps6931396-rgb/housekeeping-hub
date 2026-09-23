# Housekeeping Hub PRO — Premium Housekeeping Management Platform

A full-stack, production-ready web application built with **Flask**, **SQLite**, and
vanilla **HTML/CSS/JavaScript**. Premium SaaS-style UI with glassmorphism, dark/light
theme, dual authentication (customer + admin), full service/booking management, live
analytics dashboards, JWT-protected API layer, and CSV/PDF export.

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 + Flask (blueprint architecture) |
| Database | SQLite (via `sqlite3`, parameterized queries) |
| Web Auth | Flask signed session cookies + Werkzeug password hashing |
| API Auth | JWT (PyJWT), Bearer tokens, role-based access |
| Frontend | HTML5, CSS3 (custom design system), vanilla JS |
| Charts | Chart.js (CDN) |
| PDF Export | ReportLab |
| Fonts | Poppins / Inter (Google Fonts) |
| Prod Server | Gunicorn (`wsgi.py`, `Procfile`) |

## 2. Why sessions instead of JWT for the website

The customer/admin-facing site is **server-rendered** (Flask + Jinja2), so secure,
signed session cookies — not JWTs — are the correct and standard mechanism there
(this is what Flask, Django, and Rails all do by default). JWT is used where it
actually belongs: the **`/api/*`** JSON endpoints, intended for external/programmatic
clients such as a mobile app. See Section 7.

## 3. Project Structure

```
HousekeepingHubPro/
├── app.py                     # Application factory & entry point
├── config.py                  # Configuration (env-driven)
├── models.py                  # Database access layer
├── auth.py                    # Session decorators, JWT, reset tokens
├── utils.py                   # File uploads, pagination, CSV/PDF export
├── wsgi.py                    # Production WSGI entry point
├── Procfile                   # Gunicorn start command (Heroku/Render)
├── requirements.txt
├── .env.example
├── .gitignore
│
├── blueprints/
│   ├── public.py               # Home, services, about, contact, booking
│   ├── customer.py             # Register/login/reset/verify/dashboard
│   ├── admin.py                # Admin panel: users/services/bookings/reports
│   └── api.py                  # JWT-protected JSON API
│
├── database/
│   ├── schema.sql               # Reference schema
│   └── housekeeping.db          # Auto-created on first run
│
├── templates/
│   ├── base.html                 # Public site layout (navbar/footer/theme)
│   ├── index.html, services.html, service_detail.html
│   ├── about.html, faq.html, terms.html, privacy.html, contact.html
│   ├── booking.html, booking_confirmation.html
│   ├── 404.html, 500.html
│   ├── auth/                     # register, login, forgot/reset password,
│   │                              verify email, admin login
│   ├── customer/                 # dashboard, bookings, notifications,
│   │                              profile, change password
│   ├── admin/                    # dashboard, users, services, categories,
│   │                              bookings, reports, contacts, settings
│   └── partials/_macros.html     # Reusable Jinja macros (cards, pagination)
│
├── static/
│   ├── css/style.css              # Design system (theme, components)
│   ├── css/admin.css              # Admin panel layout
│   ├── js/main.js                 # Theme toggle, toasts, animations
│   ├── js/admin.js                # Charts, sidebar, image preview
│   ├── images/                    # Seeded default images
│   └── uploads/services/          # Admin-uploaded service images
│
└── documentation/
    ├── API_DOCUMENTATION.md
    ├── DATABASE_SCHEMA.md
    └── SETUP_GUIDE.md
```

## 4. Installation (Windows)

```bat
cd HousekeepingHubPro
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open **http://127.0.0.1:5000**. The database, default services, categories, settings,
and admin account are created automatically on first run.

### macOS / Linux
```bash
cd HousekeepingHubPro
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

### Production
```bash
pip install -r requirements.txt
gunicorn wsgi:app --workers 3 --bind 0.0.0.0:8000
```
Set real values for `SECRET_KEY`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` in `.env`
before deploying.

## 5. Default Admin Login

| Field | Value |
|---|---|
| URL | `/admin/login` |
| Email | `admin@housekeepinghub.com` |
| Password | `admin123` |

Change this immediately after first login via **Admin → Settings → Change Admin Password**,
or by setting `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env` before the database is first created.

## 6. Feature Summary

**Design system** — Royal Blue (#2563EB) / Purple (#7C3AED) / Cyan (#06B6D4) palette,
Poppins/Inter typography, glassmorphism navbar & cards, scroll-reveal animations,
animated counters, skeleton-style shimmer utility class, fully responsive (mobile/
tablet/desktop), light & dark theme with a toggle that persists via `localStorage`.

**Customer** — Register, login, forgot/reset password (token-based), email verification
(token-based), profile management, change password, browse/search/filter/paginate
services, book a service (guest or logged-in), track booking status, dashboard with
recent activity/notifications/profile overview.

**Admin** — Secure separate login, dashboard with live Chart.js analytics (bookings
trend, status split, top services, revenue), user management (search, activate/
deactivate), service management (add/edit/delete/enable-disable, image upload,
pricing, categories), category management, booking management (search/filter/
paginate, status updates, CSV + PDF export), contact message inbox, site settings.

**Security** — Passwords hashed with Werkzeug (PBKDF2), parameterized SQL throughout,
role-based `@login_required` / `@admin_required` decorators, JWT-protected `/api/*`
endpoints with role checks, file-upload validation (extension + 5 MB limit), generic
"if this email exists" messaging on forgot-password to prevent account enumeration.

**Performance/SEO** — Deferred JS, `loading="lazy"` on all content images, semantic
HTML, per-page `<title>`/meta description, `noindex` on admin pages, minimal external
requests (Google Fonts + Chart.js CDN only).

## 7. Demo-mode notes (read before evaluating)

- **Forgot password / Email verification**: no email server is configured. Both flows
  generate a real, working token/link and display it directly on the confirmation
  screen (clearly labeled "Demo mode"). Plug in an SMTP or transactional email
  provider (e.g. Flask-Mail + SendGrid) and send `reset_link` / `verify_link` by email
  instead of rendering them, and the rest of the flow needs no changes.
- **JWT API**: `/api/auth/login`, `/api/services`, `/api/bookings` (customer JWT),
  `/api/admin/stats` (admin JWT). Full docs in `documentation/API_DOCUMENTATION.md`.

## 8. Persistent storage on Render (or any host with an ephemeral disk)

By default the app uses a local SQLite file and saves uploaded images to local disk.
On free/ephemeral hosting (Render free tier, for example), that disk is wiped on every
restart or redeploy — so the database and uploaded images disappear. Two environment
variables switch the app to **persistent, free-tier** storage instead, with **no code
changes needed**:

| Variable | What it does | Free provider |
|---|---|---|
| `DATABASE_URL` | Switches the DB from SQLite to PostgreSQL | [Neon.tech](https://neon.tech) |
| `CLOUDINARY_URL` | Switches uploaded service images to cloud storage | [Cloudinary](https://cloudinary.com) |

**Setup:**
1. Create a free Neon project → copy its connection string (starts with
   `postgresql://...`) → set it as `DATABASE_URL` in Render's Environment tab.
2. Create a free Cloudinary account → on the dashboard, copy the "API Environment
   variable" (starts with `cloudinary://...`) → set it as `CLOUDINARY_URL` in Render's
   Environment tab.
3. Redeploy. On startup the app detects both variables and automatically creates the
   Postgres tables/seed data, and future service-image uploads go to Cloudinary.

Leave either variable blank to keep using local SQLite / local disk (fine for local
development only). See `documentation/SETUP_GUIDE.md` §8 for the full step-by-step
walkthrough of what to copy from each dashboard.

## 9. Full documentation

- `documentation/API_DOCUMENTATION.md` — every API endpoint, request/response shape
- `documentation/DATABASE_SCHEMA.md` — tables, columns, relationships
- `documentation/SETUP_GUIDE.md` — detailed setup, environment variables, deployment,
  and the Neon/Cloudinary persistent-storage walkthrough

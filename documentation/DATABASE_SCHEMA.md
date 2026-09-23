# Database Schema — Housekeeping Hub PRO

SQLite database at `database/housekeeping.db`, created automatically on first run from
the definitions in `models.py` (mirrored in `database/schema.sql` for reference).
`PRAGMA foreign_keys = ON` is set on every connection.

## users
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| email | TEXT UNIQUE | |
| password | TEXT | Werkzeug PBKDF2 hash, never plain text |
| phone | TEXT | nullable |
| role | TEXT | `customer` or `admin` |
| is_active | INTEGER | 1 = active, 0 = deactivated by admin |
| is_verified | INTEGER | 1 once the email-verification link is used |
| verification_token | TEXT | nullable, cleared after verification |
| avatar | TEXT | default `default-avatar.jpg` |
| reset_token | TEXT | nullable, set by forgot-password |
| reset_token_expiry | TIMESTAMP | ISO 8601, 30-minute validity |
| created_at | TIMESTAMP | default now |

## categories
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT UNIQUE | e.g. Residential, Commercial, Specialty |

## services
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| description | TEXT | |
| price | REAL | |
| image | TEXT | seeded filename (`cleaning.jpg`) or `uploads/services/<uuid>.<ext>` |
| category_id | INTEGER FK → categories.id | `ON DELETE SET NULL` |
| is_active | INTEGER | enable/disable toggle |
| created_at | TIMESTAMP | |

## bookings
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | the "Booking ID" shown to customers |
| user_id | INTEGER FK → users.id | nullable (guest bookings), `ON DELETE SET NULL` |
| name, email, phone | TEXT | snapshot of the booker's contact details |
| service_id | INTEGER FK → services.id | `ON DELETE RESTRICT` (can't delete a service with bookings) |
| date | TEXT | preferred service date, `YYYY-MM-DD` |
| notes | TEXT | optional customer notes |
| status | TEXT | `Pending` \| `Confirmed` \| `Completed` \| `Cancelled` |
| created_at | TIMESTAMP | |

## contacts
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| name, email, phone, message | TEXT | |
| created_at | TIMESTAMP | |

## notifications
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK → users.id | `ON DELETE CASCADE` |
| title, message | TEXT | |
| is_read | INTEGER | |
| created_at | TIMESTAMP | |

## activity_log
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| user_id | INTEGER FK → users.id | nullable, `ON DELETE SET NULL` |
| action | TEXT | e.g. "Logged in", "Updated booking status" |
| details | TEXT | optional free-text detail |
| created_at | TIMESTAMP | |

## settings
| Column | Type | Notes |
|---|---|---|
| key | TEXT PK | e.g. `site_name`, `support_email`, `currency_symbol` |
| value | TEXT | editable from Admin → Settings |

## Relationships
```
users (1) ───< bookings (M)        via bookings.user_id
services (1) ───< bookings (M)     via bookings.service_id
categories (1) ───< services (M)   via services.category_id
users (1) ───< notifications (M)   via notifications.user_id
users (1) ───< activity_log (M)    via activity_log.user_id
```

## Notes
- All queries use `?` parameter placeholders — no string-built SQL anywhere in the
  codebase — to prevent SQL injection.
- `setup_database()` in `models.py` is idempotent: safe to call on every startup. It
  creates tables with `CREATE TABLE IF NOT EXISTS`, seeds categories/services/admin/
  settings only if empty, and runs a lightweight column-migration guard for the
  `is_verified`/`verification_token` columns so older database files upgrade cleanly.
- **Backend portability**: the same schema and the same `?`-placeholder queries run
  against either SQLite (default, local dev) or PostgreSQL (when `DATABASE_URL` is
  set) via the compatibility layer in `db_backend.py`. Primary keys are declared as
  `INTEGER PRIMARY KEY AUTOINCREMENT` for SQLite and `SERIAL PRIMARY KEY` for
  Postgres automatically. Two queries that use SQLite-only date functions
  (`date()`, `strftime()`) branch to their PostgreSQL equivalents
  (`::date` casts, `to_char()`) in `blueprints/admin.py` based on `db.backend`.

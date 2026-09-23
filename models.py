"""
Database access layer for Housekeeping Hub PRO.

Works against either SQLite (local dev, default) or PostgreSQL (production,
when DATABASE_URL is set) via the db_backend compatibility layer. Every
query below still uses `?` placeholders and dict-style row access — the
compatibility layer translates that to whichever backend is active.
All queries are parameterized to prevent SQL injection.
"""
import os
from datetime import datetime

from flask import g, current_app
from werkzeug.security import generate_password_hash

import db_backend


# ---------------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = db_backend.connect(current_app.config)
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# Schema (backend-specific primary key syntax)
# ---------------------------------------------------------------------------
def _schema_script(backend):
    pk = "SERIAL PRIMARY KEY" if backend == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    return f"""
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL DEFAULT 'customer',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_verified INTEGER NOT NULL DEFAULT 0,
            verification_token TEXT,
            avatar TEXT DEFAULT 'default-avatar.jpg',
            reset_token TEXT,
            reset_token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS categories (
            id {pk},
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS services (
            id {pk},
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT NOT NULL,
            category_id INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id {pk},
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            service_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
            FOREIGN KEY (service_id) REFERENCES services (id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id {pk},
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id {pk},
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id {pk},
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """


# ---------------------------------------------------------------------------
# Setup / seeding
# ---------------------------------------------------------------------------
def setup_database(app):
    """Create tables if they don't exist and seed default data. Idempotent.
    Safe to call on every startup, against either SQLite or PostgreSQL."""
    cfg = app.config
    os.makedirs(os.path.dirname(cfg["DATABASE"]), exist_ok=True)
    os.makedirs(cfg["UPLOAD_FOLDER"], exist_ok=True)

    conn = db_backend.connect(cfg)
    backend = conn.backend

    conn.executescript(_schema_script(backend))
    conn.commit()

    # Lightweight migration guard: add columns if an older DB is reused
    if backend == "sqlite":
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "is_verified" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
        if "verification_token" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
        conn.commit()
    else:
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified INTEGER NOT NULL DEFAULT 0")
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token TEXT")
        conn.commit()

    # Seed categories
    if conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"] == 0:
        conn.executemany("INSERT INTO categories (name) VALUES (?)",
                          [(c,) for c in cfg["DEFAULT_CATEGORIES"]])
        conn.commit()

    category_ids = {row["name"]: row["id"] for row in conn.execute("SELECT * FROM categories").fetchall()}

    # Seed services
    if conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"] == 0:
        rows = []
        for name, cat, desc, price, image in cfg["DEFAULT_SERVICES"]:
            rows.append((name, desc, price, image, category_ids.get(cat)))
        conn.executemany(
            "INSERT INTO services (name, description, price, image, category_id) "
            "VALUES (?, ?, ?, ?, ?)", rows,
        )
        conn.commit()

    # Seed default admin
    if conn.execute("SELECT id FROM users WHERE email = ?", (cfg["ADMIN_EMAIL"],)).fetchone() is None:
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'admin')",
            ("Administrator", cfg["ADMIN_EMAIL"], generate_password_hash(cfg["ADMIN_PASSWORD"])),
        )
        conn.commit()

    # Seed settings
    for key, value in cfg["DEFAULT_SETTINGS"].items():
        if conn.execute("SELECT key FROM settings WHERE key = ?", (key,)).fetchone() is None:
            conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

    conn.close()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def get_settings():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def update_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


# ---------------------------------------------------------------------------
# Activity log & notifications
# ---------------------------------------------------------------------------
def log_activity(user_id, action, details=""):
    db = get_db()
    db.execute(
        "INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details),
    )
    db.commit()


def create_notification(user_id, title, message):
    db = get_db()
    db.execute(
        "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
        (user_id, title, message),
    )
    db.commit()


def get_notifications(user_id, unread_only=False, limit=20):
    db = get_db()
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params = [user_id]
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return db.execute(query, params).fetchall()


def unread_notification_count(user_id):
    db = get_db()
    return db.execute(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
    ).fetchone()["c"]


def mark_notifications_read(user_id):
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    db.commit()

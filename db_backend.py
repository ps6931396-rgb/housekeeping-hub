"""
Database backend compatibility layer.

The rest of the app (models.py, blueprints/*.py) writes plain SQL with
`?` placeholders and calls db.execute(query, params) exactly the way the
sqlite3 module works. This module provides a thin wrapper so the *same*
call sites also work against PostgreSQL (e.g. a free Neon.tech database)
when DATABASE_URL is configured — this is what makes data (and uploaded
service images stored as DB rows) survive restarts/redeploys on hosts with
ephemeral disks such as Render's free tier.

Backend is chosen automatically:
  - DATABASE_URL set  -> PostgreSQL (via psycopg2), persistent
  - DATABASE_URL unset -> local SQLite file, good for local development
"""
import sqlite3


class CompatCursor:
    """Wraps a raw DB-API cursor so callers can use it the same way
    regardless of backend: .fetchone(), .fetchall(), .lastrowid."""

    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class CompatConnection:
    """Wraps either a sqlite3.Connection or a psycopg2 connection behind
    one interface: execute(query_with_question_marks, params)."""

    def __init__(self, raw_conn, backend):
        self.raw = raw_conn
        self.backend = backend  # "sqlite" or "postgres"

    # --- PostgreSQL ---
    def _pg_execute(self, query, params=()):
        pg_query = query.replace("?", "%s")
        is_insert = pg_query.strip().upper().startswith("INSERT")
        # The `settings` table's primary key is `key`, not `id` — never
        # append RETURNING id for it (or any future no-id table).
        no_id_tables = ("settings",)
        table_match_no_id = any(
            pg_query.strip().upper().startswith(f"INSERT INTO {t.upper()}") for t in no_id_tables
        )
        if is_insert and "RETURNING" not in pg_query.upper() and not table_match_no_id:
            pg_query = pg_query.rstrip().rstrip(";") + " RETURNING id"

        cur = self.raw.cursor()
        cur.execute(pg_query, params)

        lastrowid = None
        if is_insert and not table_match_no_id:
            try:
                row = cur.fetchone()
                lastrowid = row["id"] if row else None
            except Exception:
                lastrowid = None
        return CompatCursor(cur, lastrowid=lastrowid)

    def execute(self, query, params=()):
        if self.backend == "sqlite":
            cur = self.raw.execute(query, params)
            return CompatCursor(cur, lastrowid=cur.lastrowid)
        return self._pg_execute(query, params)

    def executemany(self, query, seq_of_params):
        if self.backend == "sqlite":
            cur = self.raw.executemany(query, seq_of_params)
            return CompatCursor(cur)
        pg_query = query.replace("?", "%s")
        cur = self.raw.cursor()
        cur.executemany(pg_query, list(seq_of_params))
        return CompatCursor(cur)

    def executescript(self, script):
        """SQLite-only convenience (used for bulk CREATE TABLE statements)."""
        if self.backend == "sqlite":
            self.raw.executescript(script)
        else:
            cur = self.raw.cursor()
            cur.execute(script)

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def connect(config):
    """Return a CompatConnection using PostgreSQL if DATABASE_URL is set,
    otherwise local SQLite."""
    database_url = config.get("DATABASE_URL", "")

    if database_url:
        import psycopg2
        import psycopg2.extras

        raw = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        return CompatConnection(raw, backend="postgres")

    raw = sqlite3.connect(config["DATABASE"])
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return CompatConnection(raw, backend="sqlite")

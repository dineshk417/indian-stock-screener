"""
User persistence — records every authenticated visitor.
Mirrors the SQLite / PostgreSQL dual-backend pattern used in signal_logger.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

USERS_DB_PATH = Path("data_store/users.db")


def _resolve_db_url() -> Optional[str]:
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL") or st.secrets.get("SUPABASE_DB_URL")
    except Exception:
        return None


_DATABASE_URL = _resolve_db_url()
_USE_PG = False

try:
    import psycopg2  # noqa: F401
    if _DATABASE_URL:
        _USE_PG = True
        logger.info("UserStore: PostgreSQL backend active")
except ImportError:
    pass


@contextmanager
def _conn():
    if _USE_PG:
        import psycopg2 as _pg
        conn = _pg.connect(_DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()
    else:
        USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(USERS_DB_PATH), check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()


def _init_db() -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email       TEXT PRIMARY KEY,
                name        TEXT,
                avatar_url  TEXT,
                provider    TEXT DEFAULT 'google',
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                visit_count INTEGER DEFAULT 1
            )
        """)
        conn.commit()


_init_db()


def upsert_user(
    email: str,
    name: str = "",
    avatar_url: str = "",
    provider: str = "google",
) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        cur = conn.cursor()
        if _USE_PG:
            cur.execute("""
                INSERT INTO users (email, name, avatar_url, provider, first_seen, last_seen, visit_count)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (email) DO UPDATE SET
                    name        = EXCLUDED.name,
                    avatar_url  = EXCLUDED.avatar_url,
                    last_seen   = EXCLUDED.last_seen,
                    visit_count = users.visit_count + 1
            """, (email, name, avatar_url, provider, now, now))
        else:
            cur.execute("""
                INSERT INTO users (email, name, avatar_url, provider, first_seen, last_seen, visit_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(email) DO UPDATE SET
                    name        = excluded.name,
                    avatar_url  = excluded.avatar_url,
                    last_seen   = excluded.last_seen,
                    visit_count = visit_count + 1
            """, (email, name, avatar_url, provider, now, now))
        conn.commit()


def get_all_users() -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT email, name, avatar_url, provider, first_seen, last_seen, visit_count
            FROM users
            ORDER BY last_seen DESC
        """)
        cols = ["email", "name", "avatar_url", "provider", "first_seen", "last_seen", "visit_count"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

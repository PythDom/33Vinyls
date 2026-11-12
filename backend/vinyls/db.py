"""SQLite storage. One file in the data volume; schema upgraded with PRAGMA user_version."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import settings

_local = threading.local()

MIGRATIONS: list[str] = [
    # 1 — initial schema
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        display_name TEXT,
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE invites (
        code TEXT PRIMARY KEY,
        created_by INTEGER NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        used_by INTEGER REFERENCES users(id),
        used_at TEXT
    );
    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    CREATE TABLE discogs_links (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        username TEXT,
        method TEXT NOT NULL,              -- 'oauth' | 'token' | 'demo'
        token_enc TEXT NOT NULL,
        secret_enc TEXT,
        linked_at TEXT NOT NULL
    );
    CREATE TABLE oauth_pending (
        request_token TEXT PRIMARY KEY,
        request_secret TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE releases (
        id INTEGER PRIMARY KEY,           -- Discogs release id
        master_id INTEGER,
        data TEXT NOT NULL,               -- normalised JSON (see catalog.normalise_release)
        fetched_at TEXT NOT NULL
    );
    CREATE TABLE items (
        id TEXT PRIMARY KEY,              -- UUID generated on the phone
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        release_id INTEGER NOT NULL,
        kind TEXT NOT NULL,               -- 'collection' | 'want'
        fields TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL,
        deleted INTEGER NOT NULL DEFAULT 0,
        seq INTEGER NOT NULL
    );
    CREATE INDEX items_user_seq ON items(user_id, seq);
    CREATE TABLE prices (
        release_id INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        fetched_at TEXT NOT NULL
    );
    CREATE TABLE counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
    INSERT INTO counters(name, value) VALUES ('seq', 0);
    """,
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    path = str(settings.db_path)
    if conn is None or getattr(_local, "path", None) != path:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
        _local.path = path
    return conn


def migrate() -> None:
    conn = connect()
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for index, script in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.executescript("BEGIN;" + script + f"; PRAGMA user_version={index}; COMMIT;")


def reset_connection() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
    _local.conn = None


def one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return connect().execute(sql, tuple(params)).fetchone()


def all_(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return connect().execute(sql, tuple(params)).fetchall()


def run(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    return connect().execute(sql, tuple(params))


def next_seq() -> int:
    row = connect().execute("UPDATE counters SET value = value + 1 WHERE name='seq' RETURNING value").fetchone()
    return int(row[0])


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

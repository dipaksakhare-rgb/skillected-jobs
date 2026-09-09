"""SQLite connection management (WAL, foreign keys ON) — Postgres-ready call sites.

Connections are cached per-thread: the crawl pipeline issues many small statements
per job, and re-opening a WAL connection per statement is the dominant cost.
"""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import get_settings

_settings = get_settings()

_local = threading.local()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_settings.sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _thread_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """Yield the thread's cached connection; commits on success, rolls back on error."""
    conn = _thread_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def query_all(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple | dict = ()) -> int:
    """Execute a write; returns lastrowid."""
    with get_db() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)


def executemany(sql: str, seq: list[tuple | dict]) -> None:
    with get_db() as conn:
        conn.executemany(sql, seq)

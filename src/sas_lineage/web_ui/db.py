"""SQLite/Turso connection helper for the web UI."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(
    conn: sqlite3.Connection, sql: str, params: tuple = ()
) -> list[dict]:
    cur = conn.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]

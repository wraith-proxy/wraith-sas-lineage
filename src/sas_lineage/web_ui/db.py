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


def find_columns(conn: sqlite3.Connection, name: str) -> list[dict]:
    """Match columns by name or ``table.name``, case-insensitive."""
    table = None
    if "." in name:
        table, name = name.rsplit(".", 1)
    sql = (
        "SELECT c.id, c.name, t.libref, t.name AS table_name "
        "FROM columns c JOIN tables t ON t.id = c.table_id "
        "WHERE c.name LIKE ?"
    )
    params = (name,)
    if table:
        sql += " AND t.name LIKE ?"
        params = (name, table)
    sql += " ORDER BY t.libref, t.name, c.name"
    return query(conn, sql, params)

"""
Load provenance.json into a SQLite/Turso database.

Idempotent: uses INSERT OR REPLACE so re-runs are safe.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sas_lineage.ids import flag_id as make_flag_id


class ProvenanceLoader:
    """Load provenance.json entities into a SQLite/Turso database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open the database and apply the DDL schema (idempotent)."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        ddl = (
            Path(__file__).parent.parent.parent.parent / "schema" / "turso.sql"
        )
        if ddl.exists():
            self._conn.executescript(ddl.read_text())
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def load(self, provenance: Path | dict) -> None:
        """Insert all entities using INSERT OR REPLACE.

        Accepts a path to provenance.json or an already-parsed (and possibly
        enriched) dict.
        """
        data = (
            provenance
            if isinstance(provenance, dict)
            else json.loads(Path(provenance).read_text())
        )
        assert self._conn, "Call connect() first"
        conn = self._conn

        for row in data.get("tables", []):
            conn.execute(
                "INSERT OR REPLACE INTO tables "
                "(id, name, libref, engine, path, layer, is_remote, "
                "meta_id, is_intermediate) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    row["id"],
                    row["name"],
                    row["libref"],
                    row["engine"],
                    row["path"],
                    row["layer"],
                    int(row["is_remote"]),
                    row.get("meta_id"),
                    int(row.get("is_intermediate", False)),
                ),
            )

        for row in data.get("columns", []):
            conn.execute(
                "INSERT OR REPLACE INTO columns VALUES (?,?,?,?,?,?)",
                (
                    row["id"],
                    row["table_id"],
                    row["name"],
                    row["layer"],
                    row["data_type"],
                    int(row["nullable"]),
                ),
            )

        for row in data.get("jobs", []):
            conn.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?)",
                (
                    row["id"],
                    row["name"],
                    row.get("flow_id"),
                    row.get("frequency"),
                    json.dumps(row.get("frequency_evidence", [])),
                    row.get("owner"),
                    row.get("domain"),
                ),
            )

        for row in data.get("lineage_chain", []):
            conn.execute(
                "INSERT OR REPLACE INTO lineage_chain "
                "(id, mart_column_id, source_column_id, chain_order, "
                "job_id, step_name, step_type, transformation_logic, "
                "data_type_at_step, nullable_at_step, unmappable_reason, "
                "evidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["id"],
                    row["mart_column_id"],
                    row["source_column_id"],
                    row["chain_order"],
                    row["job_id"],
                    row["step_name"],
                    row["step_type"],
                    row.get("transformation_logic", ""),
                    row.get("data_type_at_step"),
                    (
                        int(row["nullable_at_step"])
                        if row.get("nullable_at_step") is not None
                        else None
                    ),
                    row.get("unmappable_reason"),
                    row.get("evidence"),
                ),
            )

        for row in data.get("table_lineage", []):
            conn.execute(
                "INSERT OR REPLACE INTO table_lineage "
                "(id, source_table_id, target_table_id, job_id, "
                "step_name, transform_type, evidence) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    row["id"],
                    row["source_table_id"],
                    row["target_table_id"],
                    row["job_id"],
                    row["step_name"],
                    row.get("transform_type", ""),
                    row.get("evidence"),
                ),
            )

        for row in data.get("quality_rules", []):
            conn.execute(
                "INSERT OR REPLACE INTO quality_rules VALUES (?,?,?,?,?)",
                (
                    row["id"],
                    row["job_id"],
                    row["rule_name"],
                    row["rule_definition"],
                    row.get("applies_to_column_id"),
                ),
            )

        for row in data.get("flags", []):
            conn.execute(
                "INSERT OR REPLACE INTO flags VALUES (?,?,?,?,?)",
                (
                    make_flag_id(row["ref_id"], row["reason"]),
                    row["ref_id"],
                    row["reason"],
                    row.get("context", ""),
                    row.get("snippet", ""),
                ),
            )

        conn.commit()

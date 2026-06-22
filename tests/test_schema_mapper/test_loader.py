"""Tests for the Turso/SQLite loader."""

import json
from pathlib import Path

import pytest

from sas_lineage.schema_mapper.loader import ProvenanceLoader

_MINIMAL_PROVENANCE = {
    "meta": {
        "generated_at": "2026-06-20T00:00:00Z",
        "parser_version": "0.0.1",
        "estate": "test",
        "job_count": 1,
        "flow_count": 1,
    },
    "tables": [
        {
            "id": "tbl_aabbccddeeff",
            "name": "ALL_EMP",
            "libref": "RISKODS",
            "engine": "BASE",
            "path": "/data/ods",
            "layer": "ODS",
            "is_remote": False,
        }
    ],
    "columns": [
        {
            "id": "col_aabbccddeeff",
            "table_id": "tbl_aabbccddeeff",
            "name": "EXPOSURE_AMT",
            "layer": "ODS",
            "data_type": "NUM",
            "nullable": True,
        }
    ],
    "jobs": [
        {
            "id": "job_aabbccddeeff",
            "name": "RISK_ODS_LOAD_DAILY",
            "flow_id": "flow_001",
            "frequency": "daily",
            "frequency_evidence": ["name_token:daily"],
            "owner": None,
            "domain": None,
        }
    ],
    "lineage_chain": [],
    "quality_rules": [],
    "flags": [],
    "reconciliation": {
        "excel_supplied": False,
        "matches": 0,
        "mismatches": [],
        "parser_only": [],
        "excel_only": [],
    },
}


@pytest.fixture()
def provenance_file(tmp_path: Path) -> Path:
    p = tmp_path / "provenance.json"
    p.write_text(json.dumps(_MINIMAL_PROVENANCE))
    return p


def test_loader_creates_tables(tmp_path: Path, provenance_file: Path):
    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(provenance_file)
    loader.close()
    assert db.exists()


def test_loader_table_count(tmp_path: Path, provenance_file: Path):
    import sqlite3

    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(provenance_file)
    loader.close()

    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
    conn.close()
    assert count == 1


def test_loader_column_count(tmp_path: Path, provenance_file: Path):
    import sqlite3

    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(provenance_file)
    loader.close()

    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM columns").fetchone()[0]
    conn.close()
    assert count == 1


def test_loader_idempotent(tmp_path: Path, provenance_file: Path):
    import sqlite3

    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(provenance_file)
    loader.load(provenance_file)
    loader.close()

    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
    conn.close()
    assert count == 1


def test_loader_job_frequency(tmp_path: Path, provenance_file: Path):
    import sqlite3

    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(provenance_file)
    loader.close()

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT frequency FROM jobs").fetchone()
    conn.close()
    assert row[0] == "daily"

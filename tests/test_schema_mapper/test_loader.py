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
            "libref": "SALESODS",
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
            "name": "ORDER_AMT",
            "layer": "ODS",
            "data_type": "NUM",
            "nullable": True,
        }
    ],
    "jobs": [
        {
            "id": "job_aabbccddeeff",
            "name": "SALES_ODS_LOAD_DAILY",
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


def test_loader_tolerates_pre_migration_provenance(
    tmp_path: Path, provenance_file: Path
):
    """_MINIMAL_PROVENANCE has no meta_id/is_intermediate/table_lineage."""
    import sqlite3

    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(provenance_file)
    loader.close()

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT meta_id, is_intermediate FROM tables"
    ).fetchone()
    conn.close()
    assert row == (None, 0)


def test_loader_table_lineage_round_trip(tmp_path: Path):
    import sqlite3

    data = dict(_MINIMAL_PROVENANCE)
    data["tables"] = [
        dict(
            _MINIMAL_PROVENANCE["tables"][0],
            meta_id="A5CGXK2Q.BE0001XY",
            is_intermediate=True,
        ),
        dict(
            _MINIMAL_PROVENANCE["tables"][0],
            id="tbl_112233445566",
            name="SALES_MART",
        ),
    ]
    data["table_lineage"] = [
        {
            "id": "tl_aabbccddeeff",
            "source_table_id": "tbl_aabbccddeeff",
            "target_table_id": "tbl_112233445566",
            "job_id": "job_aabbccddeeff",
            "step_name": "Load SALES_MART",
            "transform_type": "Table Loader",
            "evidence": "metadata_macro",
        }
    ]
    p = tmp_path / "provenance.json"
    p.write_text(json.dumps(data))

    db = tmp_path / "test.db"
    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(p)
    loader.close()

    conn = sqlite3.connect(db)
    tl = conn.execute(
        "SELECT source_table_id, target_table_id, evidence FROM table_lineage"
    ).fetchone()
    meta = conn.execute(
        "SELECT meta_id, is_intermediate FROM tables WHERE id = ?",
        ("tbl_aabbccddeeff",),
    ).fetchone()
    conn.close()
    assert tl == ("tbl_aabbccddeeff", "tbl_112233445566", "metadata_macro")
    assert meta == ("A5CGXK2Q.BE0001XY", 1)


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

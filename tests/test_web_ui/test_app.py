"""Tests for the Flask web UI."""

import sqlite3
from pathlib import Path

import pytest

from sas_lineage.web_ui.app import create_app

_SEED = """
INSERT INTO tables
    (id, name, libref, engine, path, layer, is_remote, is_intermediate)
VALUES
    ('tbl_src', 'CUSTOMER', 'RAWLIB', 'V9', '/raw', 'RAW', 0, 0),
    ('tbl_mart', 'CUST_MART', 'MARTLIB', 'V9', '/mart', 'MART', 0, 0),
    ('tbl_int', 'W99STAGE', 'work', 'BASE', '', 'RAW', 0, 1);
INSERT INTO columns VALUES
    ('col_src', 'tbl_src', 'CUST_ID', 'RAW', 'num', 1),
    ('col_mart', 'tbl_mart', 'CUST_ID', 'MART', 'num', 1),
    ('col_int', 'tbl_int', 'CUST_ID', 'RAW', 'num', 1);
INSERT INTO jobs (id, name) VALUES ('job_1', 'load_mart');
INSERT INTO lineage_chain
    (id, mart_column_id, source_column_id, chain_order,
     job_id, step_name, step_type)
VALUES
    ('lc_1', 'col_mart', 'col_src', 1, 'job_1', 'append_cust', 'DATA'),
    ('lc_2', 'col_mart', 'col_int', 2, 'job_1', 'stage_cust', 'DATA');
"""


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    ddl_path = Path(__file__).parent.parent.parent / "schema" / "turso.sql"
    if ddl_path.exists():
        conn.executescript(ddl_path.read_text())
    conn.executescript(_SEED)
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def client(db_path: Path):
    app = create_app(db_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"SAS Lineage" in resp.data


def test_provenance_picker_returns_200(client):
    resp = client.get("/provenance")
    assert resp.status_code == 200


def test_lineage_picker_returns_200(client):
    resp = client.get("/lineage")
    assert resp.status_code == 200


def test_flags_returns_200(client):
    resp = client.get("/flags")
    assert resp.status_code == 200


def test_provenance_with_unknown_col_id(client):
    resp = client.get("/provenance?col_id=col_doesnotexist")
    assert resp.status_code == 200
    assert b"No lineage found" in resp.data


def test_provenance_by_id_renders_chain(client):
    resp = client.get("/provenance?col_id=col_mart")
    assert resp.status_code == 200
    assert b"Provenance: CUST_ID" in resp.data
    assert b"append_cust" in resp.data


def test_provenance_by_qualified_name_finds_single_match(client):
    resp = client.get("/provenance?col=cust_mart.cust_id")
    assert resp.status_code == 200
    assert b"append_cust" in resp.data


def test_provenance_by_name_lists_multiple_matches(client):
    resp = client.get("/provenance?col=cust_id")
    assert resp.status_code == 200
    assert b"3 matches" in resp.data
    assert b"RAWLIB.CUSTOMER.CUST_ID" in resp.data
    assert b"MARTLIB.CUST_MART.CUST_ID" in resp.data
    assert b"work.W99STAGE.CUST_ID" in resp.data


def test_provenance_by_name_no_match(client):
    resp = client.get("/provenance?col=does_not_exist")
    assert resp.status_code == 200
    assert b"No column named" in resp.data


def test_lineage_downstream_by_id(client):
    resp = client.get("/lineage?col_id=col_src")
    assert resp.status_code == 200
    assert b"CUST_ID" in resp.data
    assert b"append_cust" in resp.data
    assert b"/provenance?col_id=col_mart" in resp.data


def test_lineage_by_qualified_name(client):
    resp = client.get("/lineage?col=customer.cust_id")
    assert resp.status_code == 200
    assert b"append_cust" in resp.data


def test_lineage_downstream_no_results(client):
    resp = client.get("/lineage?col_id=col_doesnotexist")
    assert resp.status_code == 200
    assert b"No downstream found" in resp.data


def test_provenance_shows_intermediate_hops_by_default(client):
    resp = client.get("/provenance?col_id=col_mart")
    assert b"stage_cust" in resp.data
    assert b"append_cust" in resp.data


def test_provenance_hide_intermediates_filters_hops(client):
    resp = client.get("/provenance?col_id=col_mart&hide_intermediates=1")
    assert b"stage_cust" not in resp.data
    assert b"append_cust" in resp.data

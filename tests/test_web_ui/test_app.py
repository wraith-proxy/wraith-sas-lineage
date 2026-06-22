"""Tests for the Flask web UI."""

import sqlite3
from pathlib import Path

import pytest

from sas_lineage.web_ui.app import create_app


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    ddl_path = Path(__file__).parent.parent.parent / "schema" / "turso.sql"
    if ddl_path.exists():
        conn.executescript(ddl_path.read_text())
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

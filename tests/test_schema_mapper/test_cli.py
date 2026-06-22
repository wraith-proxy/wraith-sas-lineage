"""Tests for sas-map CLI."""

import json
from pathlib import Path

from click.testing import CliRunner

from sas_lineage.schema_mapper.cli import main

_PROVENANCE = {
    "meta": {
        "generated_at": "2026-06-20T00:00:00Z",
        "parser_version": "0.0.1",
        "estate": "test",
        "job_count": 1,
        "flow_count": 0,
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
    "columns": [],
    "jobs": [
        {
            "id": "job_aabb",
            "name": "RISK_LOAD",
            "flow_id": None,
            "frequency": "daily",
            "frequency_evidence": [],
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
        "parser_only": [],
        "excel_only": [],
    },
}


def _write_provenance(tmp_path: Path) -> Path:
    p = tmp_path / "p.json"
    p.write_text(json.dumps(_PROVENANCE))
    return p


def test_cli_runs(tmp_path: Path):
    runner = CliRunner()
    p = _write_provenance(tmp_path)
    result = runner.invoke(
        main,
        [
            "--provenance",
            str(p),
            "--db",
            str(tmp_path / "l.db"),
            "--contracts-dir",
            str(tmp_path / "contracts"),
            "--gaps",
            str(tmp_path / "gaps.json"),
        ],
    )
    assert result.exit_code == 0, result.output


def test_cli_writes_db(tmp_path: Path):
    runner = CliRunner()
    p = _write_provenance(tmp_path)
    db = tmp_path / "l.db"
    runner.invoke(
        main,
        [
            "--provenance",
            str(p),
            "--db",
            str(db),
            "--contracts-dir",
            str(tmp_path / "contracts"),
            "--gaps",
            str(tmp_path / "gaps.json"),
        ],
    )
    assert db.exists()


def test_cli_writes_contracts(tmp_path: Path):
    runner = CliRunner()
    p = _write_provenance(tmp_path)
    contracts = tmp_path / "contracts"
    runner.invoke(
        main,
        [
            "--provenance",
            str(p),
            "--db",
            str(tmp_path / "l.db"),
            "--contracts-dir",
            str(contracts),
            "--gaps",
            str(tmp_path / "gaps.json"),
        ],
    )
    assert contracts.exists()
    ymls = list(contracts.glob("*.yml"))
    assert len(ymls) >= 1


def test_cli_writes_gaps(tmp_path: Path):
    runner = CliRunner()
    p = _write_provenance(tmp_path)
    gaps = tmp_path / "gaps.json"
    runner.invoke(
        main,
        [
            "--provenance",
            str(p),
            "--db",
            str(tmp_path / "l.db"),
            "--contracts-dir",
            str(tmp_path / "contracts"),
            "--gaps",
            str(gaps),
        ],
    )
    assert gaps.exists()

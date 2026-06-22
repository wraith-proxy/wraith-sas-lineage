"""Tests for sas-parse CLI."""

import json
from pathlib import Path

from click.testing import CliRunner

from sas_lineage.parser.cli import main

_FIXTURE = Path(__file__).parent / "fixtures"


def test_cli_runs(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--code-dir",
            str(_FIXTURE),
            "--log-dir",
            str(_FIXTURE),
            "--estate",
            "test",
            "--output",
            str(tmp_path / "p.json"),
            "--report",
            str(tmp_path / "r.json"),
        ],
    )
    assert result.exit_code == 0, result.output


def test_cli_writes_provenance(tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "p.json"
    runner.invoke(
        main,
        [
            "--code-dir",
            str(_FIXTURE),
            "--log-dir",
            str(_FIXTURE),
            "--estate",
            "test",
            "--output",
            str(out),
            "--report",
            str(tmp_path / "r.json"),
        ],
    )
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["meta"]["estate"] == "test"


def test_cli_writes_report(tmp_path: Path):
    runner = CliRunner()
    report = tmp_path / "r.json"
    runner.invoke(
        main,
        [
            "--code-dir",
            str(_FIXTURE),
            "--log-dir",
            str(_FIXTURE),
            "--estate",
            "test",
            "--output",
            str(tmp_path / "p.json"),
            "--report",
            str(report),
        ],
    )
    assert report.exists()
    data = json.loads(report.read_text())
    assert "job_count" in data
    assert "flag_count" in data


def test_cli_flag_count_in_report(tmp_path: Path):
    runner = CliRunner()
    report = tmp_path / "r.json"
    runner.invoke(
        main,
        [
            "--code-dir",
            str(_FIXTURE),
            "--log-dir",
            str(_FIXTURE),
            "--estate",
            "test",
            "--output",
            str(tmp_path / "p.json"),
            "--report",
            str(report),
        ],
    )
    data = json.loads(report.read_text())
    assert data["flag_count"] >= 1
    assert "remote_execution" in data["flags_by_reason"]

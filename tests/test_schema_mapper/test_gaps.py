"""Tests for the gaps report generator."""

import json
from pathlib import Path

from sas_lineage.schema_mapper.gaps import generate_gaps_report

_PROVENANCE = {
    "jobs": [
        {"id": "j1", "name": "JOB_NO_OWNER", "owner": None, "domain": None},
        {
            "id": "j2",
            "name": "JOB_WITH_OWNER",
            "owner": "Alice",
            "domain": "risk",
        },
    ],
    "flags": [
        {
            "ref_id": "lc_abc",
            "reason": "macro_unresolved",
            "context": "test",
            "snippet": "&x",
        }
    ],
    "quality_rules": [
        {
            "id": "qr1",
            "job_id": "j1",
            "rule_name": "R1",
            "rule_definition": "x > 0",
            "applies_to_column_id": None,
        },
        {
            "id": "qr2",
            "job_id": "j2",
            "rule_name": "R2",
            "rule_definition": "y > 0",
            "applies_to_column_id": "col_abc",
        },
    ],
}


def test_gaps_missing_owner(tmp_path: Path):
    out = tmp_path / "gaps.json"
    gaps = generate_gaps_report(_PROVENANCE, out)
    names = [g["job_name"] for g in gaps["missing_owner"]]
    assert "JOB_NO_OWNER" in names
    assert "JOB_WITH_OWNER" not in names


def test_gaps_missing_domain(tmp_path: Path):
    out = tmp_path / "gaps.json"
    gaps = generate_gaps_report(_PROVENANCE, out)
    names = [g["job_name"] for g in gaps["missing_domain"]]
    assert "JOB_NO_OWNER" in names


def test_gaps_flagged_columns(tmp_path: Path):
    out = tmp_path / "gaps.json"
    gaps = generate_gaps_report(_PROVENANCE, out)
    refs = [f["ref_id"] for f in gaps["flagged_columns"]]
    assert "lc_abc" in refs


def test_gaps_unmapped_quality_rules(tmp_path: Path):
    out = tmp_path / "gaps.json"
    gaps = generate_gaps_report(_PROVENANCE, out)
    names = [r["rule_name"] for r in gaps["unmapped_quality_rules"]]
    assert "R1" in names
    assert "R2" not in names


def test_gaps_writes_json(tmp_path: Path):
    out = tmp_path / "gaps.json"
    generate_gaps_report(_PROVENANCE, out)
    assert out.exists()
    parsed = json.loads(out.read_text())
    assert "missing_owner" in parsed

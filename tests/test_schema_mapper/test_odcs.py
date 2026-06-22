"""Tests for ODCS contract generation."""

from pathlib import Path

import yaml

from sas_lineage.schema_mapper.odcs import generate_contract

_TABLE = {
    "id": "tbl_aabbccddeeff",
    "name": "ALL_EMP",
    "libref": "RISKODS",
    "engine": "BASE",
    "path": "/data/ods",
    "layer": "ODS",
    "is_remote": False,
}
_COLUMNS = [
    {
        "id": "col_aabbccddeeff",
        "table_id": "tbl_aabbccddeeff",
        "name": "EXPOSURE_AMT",
        "data_type": "NUM",
        "nullable": True,
        "layer": "ODS",
    }
]
_JOB = {
    "id": "job_aabb",
    "name": "RISK_LOAD",
    "frequency": "daily",
    "frequency_evidence": ["name_token:daily"],
    "owner": "Alice",
    "domain": "risk",
}
_QUALITY_RULES = [
    {
        "id": "qr_aabb",
        "job_id": "job_aabb",
        "rule_name": "NON_NEGATIVE",
        "rule_definition": "EXPOSURE_AMT >= 0",
        "applies_to_column_id": "col_aabbccddeeff",
    }
]


def test_contract_created(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    assert out.exists()


def test_contract_is_valid_yaml(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    parsed = yaml.safe_load(out.read_text())
    assert parsed["name"] == "ALL_EMP"


def test_contract_has_schema(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    parsed = yaml.safe_load(out.read_text())
    assert "schema" in parsed
    assert parsed["schema"]["layer"] == "ODS"


def test_contract_has_columns(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    parsed = yaml.safe_load(out.read_text())
    cols = parsed["schema"]["columns"]
    assert len(cols) == 1
    assert cols[0]["name"] == "EXPOSURE_AMT"


def test_contract_has_quality_rules(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    parsed = yaml.safe_load(out.read_text())
    assert len(parsed["quality"]) == 1
    assert parsed["quality"][0]["name"] == "NON_NEGATIVE"


def test_contract_owner_and_domain(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    parsed = yaml.safe_load(out.read_text())
    assert parsed["owner"] == "Alice"
    assert parsed["domain"] == "risk"


def test_contract_freshness(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    parsed = yaml.safe_load(out.read_text())
    assert parsed["freshness"]["frequency"] == "daily"


def test_contract_no_job(tmp_path: Path):
    out = generate_contract(_TABLE, _COLUMNS, None, [], [], tmp_path)
    parsed = yaml.safe_load(out.read_text())
    assert parsed["owner"] is None


def test_contract_filename_includes_layer(tmp_path: Path):
    out = generate_contract(
        _TABLE, _COLUMNS, _JOB, _QUALITY_RULES, [], tmp_path
    )
    assert "ODS" in out.name

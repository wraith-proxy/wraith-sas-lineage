"""Tests for the manual Tool 2 inputs (owner/domain, quality params)."""

from pathlib import Path

from sas_lineage.schema_mapper.enrich import load_owners, load_quality_rules


def test_load_owners(tmp_path: Path):
    p = tmp_path / "owners.csv"
    p.write_text("job,owner,domain\nRISK_LOAD,Risk Team,Credit\n")
    owners = load_owners(p)
    assert owners["RISK_LOAD"]["owner"] == "Risk Team"
    assert owners["RISK_LOAD"]["domain"] == "Credit"


def test_load_owners_blank_domain_is_none(tmp_path: Path):
    p = tmp_path / "owners.csv"
    p.write_text("job,owner,domain\nRISK_LOAD,Risk Team,\n")
    owners = load_owners(p)
    assert owners["RISK_LOAD"]["domain"] is None


def test_load_quality_rules_keys_by_job_name(tmp_path: Path):
    p = tmp_path / "params.csv"
    p.write_text(
        "job,rule_name,rule_definition,column_id\n"
        "RISK_LOAD,NON_NEG,EXP >= 0,col_abc\n"
    )
    jobs = [{"id": "job_123", "name": "RISK_LOAD"}]
    rules = load_quality_rules(p, jobs)
    assert len(rules) == 1
    assert rules[0]["job_id"] == "job_123"
    assert rules[0]["rule_name"] == "NON_NEG"
    assert rules[0]["applies_to_column_id"] == "col_abc"


def test_load_quality_rules_skips_unknown_job(tmp_path: Path):
    p = tmp_path / "params.csv"
    p.write_text(
        "job,rule_name,rule_definition,column_id\n"
        "GHOST_JOB,NON_NEG,EXP >= 0,\n"
    )
    rules = load_quality_rules(p, [{"id": "job_1", "name": "RISK_LOAD"}])
    assert rules == []

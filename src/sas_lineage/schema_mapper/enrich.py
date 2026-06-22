"""
Manual Tool 2 inputs: owner/domain and the quality-rule parameters table.

Both are CSV, keyed by job name (the clean, readable form the plan calls for).
Neither overwrites parser output. They add the human-supplied facts the parser
cannot know.

  owners.csv   : job,owner,domain
  params.csv   : job,rule_name,rule_definition,column_id   (column_id optional)
"""

from __future__ import annotations

import csv
from pathlib import Path

from sas_lineage.ids import quality_rule_id as make_qr_id


def load_owners(path: Path) -> dict[str, dict[str, str | None]]:
    """Return {job_name: {"owner": ..., "domain": ...}} from a CSV."""
    out: dict[str, dict[str, str | None]] = {}
    for row in _rows(path):
        job = (row.get("job") or "").strip()
        if not job:
            continue
        out[job] = {
            "owner": (row.get("owner") or "").strip() or None,
            "domain": (row.get("domain") or "").strip() or None,
        }
    return out


def load_quality_rules(path: Path, jobs: list[dict]) -> list[dict]:
    """Build quality_rule dicts from a CSV, keyed to jobs by name."""
    job_id_by_name = {j["name"]: j["id"] for j in jobs}
    rules: list[dict] = []
    for row in _rows(path):
        job_name = (row.get("job") or "").strip()
        rule_name = (row.get("rule_name") or "").strip()
        job_id = job_id_by_name.get(job_name)
        if not job_id or not rule_name:
            continue
        rules.append(
            {
                "id": make_qr_id(job_id, rule_name),
                "job_id": job_id,
                "rule_name": rule_name,
                "rule_definition": (row.get("rule_definition") or "").strip(),
                "applies_to_column_id": (row.get("column_id") or "").strip()
                or None,
            }
        )
    return rules


def _rows(path: Path) -> list[dict]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))

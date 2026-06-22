"""
Gaps report: surfaces missing owners, domains, quality rules, and flagged
columns.

Output: mapping_gaps.json
"""

from __future__ import annotations

import json
from pathlib import Path


def generate_gaps_report(provenance: dict, output_path: Path) -> dict:
    gaps: dict = {
        "missing_owner": [],
        "missing_domain": [],
        "flagged_columns": [],
        "unmapped_quality_rules": [],
    }

    for job in provenance.get("jobs", []):
        if not job.get("owner"):
            gaps["missing_owner"].append(
                {"job_id": job["id"], "job_name": job["name"]}
            )
        if not job.get("domain"):
            gaps["missing_domain"].append(
                {"job_id": job["id"], "job_name": job["name"]}
            )

    for flag in provenance.get("flags", []):
        gaps["flagged_columns"].append(
            {
                "ref_id": flag["ref_id"],
                "reason": flag["reason"],
                "context": flag["context"],
            }
        )

    for rule in provenance.get("quality_rules", []):
        if not rule.get("applies_to_column_id"):
            gaps["unmapped_quality_rules"].append(
                {
                    "rule_id": rule["id"],
                    "rule_name": rule["rule_name"],
                    "job_id": rule["job_id"],
                }
            )

    output_path.write_text(json.dumps(gaps, indent=2))
    return gaps

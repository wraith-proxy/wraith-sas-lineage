"""
ODCS contract generator: one contract per data product (table at layer).

Emits best-effort contracts even for flagged/incomplete columns. Flags are
carried into the contract so the UI and humans can see them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def generate_contract(
    table: dict,
    columns: list[dict],
    job: dict | None,
    quality_rules: list[dict],
    flags: list[dict],
    output_dir: Path,
) -> Path:
    """Generate one ODCS YAML contract for a table."""
    contract: dict[str, Any] = {
        "apiVersion": "v2.3.0",
        "kind": "DataContract",
        "id": table["id"],
        "name": table["name"],
        "version": "0.0.1",
        "status": "draft",
        "domain": job.get("domain") if job else None,
        "owner": job.get("owner") if job else None,
        "freshness": _freshness(job),
        "schema": {
            "type": "table",
            "physicalName": f"{table['libref']}.{table['name']}",
            "layer": table["layer"],
            "engine": table["engine"],
            "columns": [_column_def(c, flags) for c in columns],
        },
        "quality": [_quality_rule(r) for r in quality_rules],
        "lineageFlags": [
            f for f in flags if _flag_ref_is_for_table(f, table["id"], columns)
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{table['layer']}_{table['name']}.yml"
    out_path.write_text(
        yaml.dump(contract, sort_keys=False, allow_unicode=True)
    )
    return out_path


def _freshness(job: dict | None) -> dict:
    if not job:
        return {"frequency": None, "evidence": []}
    return {
        "frequency": job.get("frequency"),
        "evidence": job.get("frequency_evidence", []),
    }


def _column_def(col: dict, flags: list[dict]) -> dict:
    col_flags = [
        f["reason"] for f in flags if col["id"] in f.get("ref_id", "")
    ]
    return {
        "name": col["name"],
        "dataType": col["data_type"],
        "nullable": col["nullable"],
        "flags": col_flags or None,
    }


def _quality_rule(rule: dict) -> dict:
    return {
        "name": rule["rule_name"],
        "rule": rule["rule_definition"],
        "columnId": rule.get("applies_to_column_id"),
    }


def _flag_ref_is_for_table(
    flag: dict, table_id: str, columns: list[dict]
) -> bool:
    col_ids = {c["id"] for c in columns}
    return flag.get("ref_id", "") in col_ids or table_id in flag.get(
        "ref_id", ""
    )

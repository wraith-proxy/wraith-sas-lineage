"""
Intended-vs-executed diff: compare static-parse lineage against the log.

Edges parsed from code or DI metadata are the *intended* lineage; edges
the MPRINT log confirmed (or revealed) are the *executed* lineage. The
gap between them is where an estate lies to you.

Output: lineage_diff.json
"""

from __future__ import annotations

import json
from pathlib import Path

_EXECUTED = "log_confirmed"
_LOG_ONLY_MARK = "log-only edge"


def _slim(edge: dict) -> dict:
    return {
        "id": edge["id"],
        "mart_column_id": edge["mart_column_id"],
        "source_column_id": edge["source_column_id"],
        "step_name": edge["step_name"],
        "job_id": edge["job_id"],
        "evidence": edge.get("evidence"),
    }


def generate_diff_report(provenance: dict, output_path: Path) -> dict:
    chains = provenance.get("lineage_chain", [])
    log_only_ids = {
        f["ref_id"]
        for f in provenance.get("flags", [])
        if f.get("reason") == "hand_written_code"
        and _LOG_ONLY_MARK in f.get("context", "")
    }

    intended_not_executed = []
    executed = []
    unattributed = []
    for edge in chains:
        evidence = edge.get("evidence")
        if evidence == _EXECUTED:
            executed.append(edge)
        elif evidence is None:
            unattributed.append(edge)
        else:
            intended_not_executed.append(edge)

    executed_not_intended = [e for e in executed if e["id"] in log_only_ids]

    diff = {
        "summary": {
            "edges": len(chains),
            "executed": len(executed),
            "intended_not_executed": len(intended_not_executed),
            "executed_not_intended": len(executed_not_intended),
            "unattributed": len(unattributed),
        },
        "intended_not_executed": [_slim(e) for e in intended_not_executed],
        "executed_not_intended": [_slim(e) for e in executed_not_intended],
    }
    output_path.write_text(json.dumps(diff, indent=2))
    return diff

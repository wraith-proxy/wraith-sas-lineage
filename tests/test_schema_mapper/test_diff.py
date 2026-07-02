"""Intended-vs-executed diff report tests (eval B8)."""

import json
from pathlib import Path

from sas_lineage.schema_mapper.diff import generate_diff_report


def _edge(edge_id: str, evidence: str | None) -> dict:
    return {
        "id": edge_id,
        "mart_column_id": "col_m",
        "source_column_id": "col_s",
        "chain_order": 1,
        "job_id": "job_1",
        "step_name": "step",
        "step_type": "DATA",
        "transformation_logic": "",
        "evidence": evidence,
    }


def test_diff_buckets(tmp_path: Path):
    provenance = {
        "lineage_chain": [
            _edge("lc_intended", "parsed_sql"),
            _edge("lc_meta", "metadata_macro"),
            _edge("lc_confirmed", "log_confirmed"),
            _edge("lc_logonly", "log_confirmed"),
            _edge("lc_old", None),
        ],
        "flags": [
            {
                "ref_id": "lc_logonly",
                "reason": "hand_written_code",
                "context": (
                    "log-only edge: executed but absent from static parse"
                ),
                "snippet": "",
            }
        ],
    }
    out = tmp_path / "diff.json"
    diff = generate_diff_report(provenance, out)

    assert diff["summary"] == {
        "edges": 5,
        "executed": 2,
        "intended_not_executed": 2,
        "executed_not_intended": 1,
        "unattributed": 1,
    }
    assert {e["id"] for e in diff["intended_not_executed"]} == {
        "lc_intended",
        "lc_meta",
    }
    assert [e["id"] for e in diff["executed_not_intended"]] == ["lc_logonly"]
    assert json.loads(out.read_text()) == diff


def test_diff_empty_provenance(tmp_path: Path):
    out = tmp_path / "diff.json"
    diff = generate_diff_report({}, out)
    assert diff["summary"]["edges"] == 0
    assert out.exists()


def test_builder_flags_log_only_edges(tmp_path: Path):
    """End-to-end: log-only hop carries the marker the diff keys on."""
    from sas_lineage.parser.builder import ProvenanceBuilder
    from sas_lineage.parser.extractors.data_step import DataStepExtractor

    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    code_dir.mkdir()
    log_dir.mkdir()
    (code_dir / "J.sas").write_text("%load_sales(in=SRC, out=STG);\n")
    (log_dir / "J.log").write_text(
        "MPRINT(LOAD_SALES):   data SALESODS.STG;\n"
        "MPRINT(LOAD_SALES):   set SALESODS.SRC;\n"
        "MPRINT(LOAD_SALES):   AMOUNT = QTY * PRICE;\n"
        "MPRINT(LOAD_SALES):   run;\n"
    )
    b = ProvenanceBuilder(code_dir, log_dir, estate="t")
    b.register(DataStepExtractor())
    prov = b.build()

    diff = generate_diff_report(
        json.loads(prov.to_json()), tmp_path / "diff.json"
    )
    assert diff["summary"]["executed_not_intended"] >= 1

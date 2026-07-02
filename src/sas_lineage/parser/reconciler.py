"""
Reconciler: compares parser output against a manual Excel mapping.

Excel never overwrites parser output. Mismatches are flagged for human review.
"""

from __future__ import annotations

from pathlib import Path

from sas_lineage.models import ReconciliationResult


def reconcile(
    provenance_columns: dict[str, str],
    excel_path: Path | None,
) -> ReconciliationResult:
    """
    Compare parser-discovered column mappings against an Excel override.

    provenance_columns: {source_col_id -> mart_col_id}
    excel_path: optional path to .xlsx with columns [source, target, job]

    Returns ReconciliationResult with match/mismatch counts.
    """
    if excel_path is None or not excel_path.exists():
        return ReconciliationResult(excel_supplied=False)

    excel_rows = _load_excel(excel_path)
    matches = 0
    mismatches: list[str] = []
    parser_only: list[str] = []
    excel_only: list[str] = []

    excel_keys = {(r["source"], r["target"]) for r in excel_rows}
    excel_targets: dict[str, set[str]] = {}
    for r in excel_rows:
        excel_targets.setdefault(r["source"], set()).add(r["target"])
    parser_keys = set(provenance_columns.items())

    for src, tgt in parser_keys:
        if (src, tgt) in excel_keys:
            matches += 1
        elif src in excel_targets:
            # Same source, different target: a genuine conflict to review.
            mismatches.append(
                f"{src}->{tgt} (excel: {sorted(excel_targets[src])})"
            )
        else:
            parser_only.append(f"{src}->{tgt}")

    for r in excel_rows:
        if (r["source"], r["target"]) not in parser_keys:
            excel_only.append(f"{r['source']}->{r['target']}")

    return ReconciliationResult(
        excel_supplied=True,
        matches=matches,
        mismatches=mismatches,
        parser_only=parser_only,
        excel_only=excel_only,
    )


def _load_excel(path: Path) -> list[dict]:
    """Load Excel mapping sheet. Expects columns: source, target, job."""
    try:
        import openpyxl
    except ImportError:
        return []

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).lower().strip() for h in rows[0]]
    return [dict(zip(headers, row)) for row in rows[1:] if any(row)]

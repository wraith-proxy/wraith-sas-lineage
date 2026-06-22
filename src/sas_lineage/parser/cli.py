"""CLI entry point for the SAS Parser (Tool 1)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import click

from sas_lineage.parser.builder import ProvenanceBuilder
from sas_lineage.parser.extractors.data_step import DataStepExtractor
from sas_lineage.parser.extractors.libname import LibnameExtractor
from sas_lineage.parser.extractors.macro_call import MacroCallExtractor
from sas_lineage.parser.extractors.proc_generic import GenericProcExtractor
from sas_lineage.parser.extractors.proc_sql import ProcSqlExtractor
from sas_lineage.parser.extractors.rsubmit import RsubmitExtractor
from sas_lineage.parser.extractors.scd2 import Scd2Extractor
from sas_lineage.parser.reconciler import reconcile


@click.command()
@click.option(
    "--code-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Root directory containing all deployed .sas files.",
)
@click.option(
    "--log-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Root directory containing verbose .log files from SAS execution.",
)
@click.option(
    "--estate",
    default="sas-estate",
    show_default=True,
    help="Estate name to embed in provenance.json metadata.",
)
@click.option(
    "--output",
    default="provenance.json",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Output path for provenance.json.",
)
@click.option(
    "--report",
    default="parse_report.json",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Output path for parse_report.json.",
)
@click.option(
    "--excel",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Optional manual mapping .xlsx (source, target, job) to reconcile.",
)
def main(
    code_dir: Path,
    log_dir: Path,
    estate: str,
    output: Path,
    report: Path,
    excel: Path | None,
) -> None:
    """Extract lineage from SAS code and logs, emit provenance.json."""
    builder = ProvenanceBuilder(code_dir, log_dir, estate=estate)
    builder.register(LibnameExtractor())
    builder.register(DataStepExtractor())
    builder.register(ProcSqlExtractor())
    builder.register(GenericProcExtractor())
    builder.register(RsubmitExtractor())
    builder.register(Scd2Extractor())
    builder.register(MacroCallExtractor())

    provenance = builder.build()

    if excel:
        mapping = {
            hop.source_column_id: hop.mart_column_id
            for hop in provenance.lineage_chain
        }
        provenance.reconciliation = reconcile(mapping, excel)

    output.write_text(provenance.to_json())
    click.echo(f"Wrote provenance: {output}")

    parse_report = {
        "job_count": provenance.meta.job_count,
        "flow_count": provenance.meta.flow_count,
        "table_count": len(provenance.tables),
        "column_count": len(provenance.columns),
        "lineage_chain_count": len(provenance.lineage_chain),
        "flag_count": len(provenance.flags),
        "flags_by_reason": dict(
            Counter(f.reason.value for f in provenance.flags)
        ),
        "reconciliation": {
            "excel_supplied": provenance.reconciliation.excel_supplied,
            "matches": provenance.reconciliation.matches,
            "mismatches": len(provenance.reconciliation.mismatches),
            "parser_only": len(provenance.reconciliation.parser_only),
            "excel_only": len(provenance.reconciliation.excel_only),
        },
    }
    report.write_text(json.dumps(parse_report, indent=2))
    click.echo(f"Wrote report: {report}")

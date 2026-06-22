"""CLI entry point for the Schema Mapper (Tool 2)."""

from __future__ import annotations

import json
from pathlib import Path

import click

from sas_lineage.schema_mapper.enrich import load_owners, load_quality_rules
from sas_lineage.schema_mapper.gaps import generate_gaps_report
from sas_lineage.schema_mapper.loader import ProvenanceLoader
from sas_lineage.schema_mapper.odcs import generate_contract


@click.command()
@click.option(
    "--provenance",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to provenance.json (output from sas-parse).",
)
@click.option(
    "--db",
    default="lineage.db",
    show_default=True,
    type=click.Path(path_type=Path),
    help="SQLite database output path for lineage queries.",
)
@click.option(
    "--contracts-dir",
    default="contracts",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory for generated ODCS YAML contracts.",
)
@click.option(
    "--gaps",
    default="mapping_gaps.json",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path for the gaps report.",
)
@click.option(
    "--owners",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Optional owner/domain CSV (job,owner,domain).",
)
@click.option(
    "--params",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Optional quality CSV (job,rule_name,rule_definition,column_id).",
)
def main(
    provenance: Path,
    db: Path,
    contracts_dir: Path,
    gaps: Path,
    owners: Path | None,
    params: Path | None,
) -> None:
    """Load provenance into a database and generate ODCS data contracts."""
    data = json.loads(provenance.read_text())

    if owners:
        owner_map = load_owners(owners)
        for job in data.get("jobs", []):
            manual = owner_map.get(job["name"])
            if manual:
                job["owner"] = manual["owner"]
                job["domain"] = manual["domain"]

    if params:
        data["quality_rules"] = load_quality_rules(
            params, data.get("jobs", [])
        )

    loader = ProvenanceLoader(db)
    loader.connect()
    loader.load(data)
    loader.close()
    click.echo(f"Loaded into database: {db}")

    col_to_table = {c["id"]: c["table_id"] for c in data.get("columns", [])}
    col_by_table: dict[str, list] = {}
    for col in data.get("columns", []):
        col_by_table.setdefault(col["table_id"], []).append(col)

    job_index = {j["id"]: j for j in data.get("jobs", [])}
    qr_by_job: dict[str, list] = {}
    for qr in data.get("quality_rules", []):
        qr_by_job.setdefault(qr["job_id"], []).append(qr)

    # A table is owned by the job that writes its (mart) columns. Recover the
    # link through the lineage chain, which carries job_id.
    table_job: dict[str, str] = {}
    for hop in data.get("lineage_chain", []):
        tid = col_to_table.get(hop["mart_column_id"])
        if tid and tid not in table_job:
            table_job[tid] = hop["job_id"]

    for table in data.get("tables", []):
        job = job_index.get(table_job.get(table["id"]))
        out = generate_contract(
            table=table,
            columns=col_by_table.get(table["id"], []),
            job=job,
            quality_rules=qr_by_job.get(job["id"], []) if job else [],
            flags=data.get("flags", []),
            output_dir=contracts_dir,
        )
        click.echo(f"  contract: {out}")

    generate_gaps_report(data, gaps)
    click.echo(f"Wrote gaps report: {gaps}")

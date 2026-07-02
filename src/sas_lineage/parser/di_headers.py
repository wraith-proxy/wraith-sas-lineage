"""DI Studio artefact harvester: builder pre-pass over RAW code.

DI-generated jobs open every transformation step with a boxed comment
carrying the step name, transform type, and Source/Target table lines
annotated with metadata-repository object IDs. Headers are comments, so
this runs on raw code before the splitter's comment stripping deletes
them (see .claude/knowledge/gotchas.md).

Each header also owns the text span down to the next header. Where DI
emitted a mapping tab, that span carries `_OUTPUT{n}_col{N}_*` %LET
families: per-target-column name, type, derivation expression (`_exp`)
and input column list. Inputs are unqualified (no `_input_table`
variable exists — unfixed in DI since at least 2012), so column edges
are only attributed when the header names exactly one source table;
with several source tables every mapped column gets a `multi_source`
flag instead, for the SQL fallback to resolve.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from sas_lineage.ids import lineage_chain_id, table_lineage_id
from sas_lineage.ids import table_id as make_table_id
from sas_lineage.models import (
    Column,
    Evidence,
    Flag,
    LineageChain,
    StepType,
    Table,
    TableLineage,
    UnmappableReason,
)
from sas_lineage.parser.extractors._factory import new_column, new_table
from sas_lineage.parser.sql_tokeniser import (
    extract_sql_tables,
    qualified_column_refs,
)

_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_STEP_LINE = re.compile(r"^\s*\*?\s*Step:\s*(.+?)\s*\**\s*$", re.MULTILINE)
_TRANSFORM_LINE = re.compile(
    r"^\s*\*?\s*Transform:\s*(.+?)\s*\**\s*$", re.MULTILINE
)
_TABLE_LINE = re.compile(
    r"^\s*\*?\s*(Source|Target)\s+Table:\s*"
    r"([A-Za-z_]\w{0,7})\.(\w+)"
    r"[^(\r\n]*"
    r"\((\w+\.\w+)\)",
    re.MULTILINE | re.IGNORECASE,
)
_LET_OUTPUT_COL = re.compile(
    r"%let\s+_OUTPUT(\d+)_col(\d+)_(\w+)\s*=\s*([^;]*);",
    re.IGNORECASE,
)
_LET_OUTPUT_TABLE = re.compile(
    r"%let\s+_OUTPUT(\d+)\s*=\s*([^;]*);", re.IGNORECASE
)
_LET_SYSLAST = re.compile(
    r"%let\s+SYSLAST\s*=\s*(?:%\w+\s*\()?\s*"
    r"([A-Za-z_]\w{0,7}(?:\.\w+)?)\s*\)?\s*;",
    re.IGNORECASE,
)

_SAS_TYPE = {"N": "NUM", "C": "CHAR"}


class DiHarvest(NamedTuple):
    tables: list[Table]
    table_edges: list[TableLineage]
    columns: list[Column]
    column_edges: list[LineageChain]
    flags: list[Flag]


class _Step(NamedTuple):
    name: str
    transform_type: str
    sources: list[Table]
    targets: list[Table]
    span: str


def harvest_di_headers(code: str, job_id: str) -> DiHarvest:
    """Extract DI tables, table edges, and mapped column edges.

    A comment block counts as a step header only if it carries a Step:
    line. A malformed header/mapping line simply does not match and
    contributes nothing — the executable code below is still parsed by
    the ordinary extractors, so no lineage is lost, only the metadata.
    """
    tables: dict[str, Table] = {}
    table_edges: list[TableLineage] = []
    columns: dict[str, Column] = {}
    column_edges: list[LineageChain] = []
    flags: list[Flag] = []

    steps = _parse_steps(code, tables)

    edge_ids: set[str] = set()

    def _add_edge(edge: TableLineage) -> None:
        if edge.id not in edge_ids:
            edge_ids.add(edge.id)
            table_edges.append(edge)

    for step in steps:
        for src in step.sources:
            for tgt in step.targets:
                _add_edge(
                    TableLineage(
                        id=table_lineage_id(src.id, tgt.id, step.name),
                        source_table_id=src.id,
                        target_table_id=tgt.id,
                        job_id=job_id,
                        step_name=step.name,
                        transform_type=step.transform_type,
                        evidence=Evidence.METADATA_MACRO,
                    )
                )
        _harvest_mapping(step, job_id, tables, columns, column_edges, flags)

    _harvest_syslast(code, job_id, steps, tables, _add_edge)

    return DiHarvest(
        list(tables.values()),
        table_edges,
        list(columns.values()),
        column_edges,
        flags,
    )


def _harvest_syslast(
    code: str,
    job_id: str,
    steps: list[_Step],
    tables: dict[str, Table],
    add_edge,
) -> None:
    """Chain consecutive %let SYSLAST assignments into table edges.

    DI steps hand their output to the next step via SYSLAST, so each
    consecutive pair is a step-to-step edge. Header-derived edges carry
    the same (source, target, step) triple and win by id de-dupe; this
    only adds flow where headers are missing or degraded.
    """
    header_spans = [
        (m.start(), _STEP_LINE.search(m.group(0)))
        for m in _COMMENT_BLOCK.finditer(code)
        if _STEP_LINE.search(m.group(0))
    ]

    def _step_name_at(pos: int) -> str:
        name = "SYSLAST"
        for start, step_m in header_spans:
            if start <= pos:
                name = step_m.group(1)
            else:
                break
        return name

    prev: Table | None = None
    for m in _LET_SYSLAST.finditer(code):
        current = _resolve_table(m.group(1), tables)
        if prev is not None and prev.id != current.id:
            step_name = _step_name_at(m.start())
            add_edge(
                TableLineage(
                    id=table_lineage_id(prev.id, current.id, step_name),
                    source_table_id=prev.id,
                    target_table_id=current.id,
                    job_id=job_id,
                    step_name=step_name,
                    transform_type="",
                    evidence=Evidence.METADATA_MACRO,
                )
            )
        prev = current


def _parse_steps(code: str, tables: dict[str, Table]) -> list[_Step]:
    headers: list[tuple[int, int, str]] = []
    for m in _COMMENT_BLOCK.finditer(code):
        if _STEP_LINE.search(m.group(0)):
            headers.append((m.start(), m.end(), m.group(0)))

    steps: list[_Step] = []
    for i, (_, end, block) in enumerate(headers):
        step_m = _STEP_LINE.search(block)
        transform_m = _TRANSFORM_LINE.search(block)
        sources: list[Table] = []
        targets: list[Table] = []
        for t in _TABLE_LINE.finditer(block):
            role, libref, name, meta_id = t.groups()
            tbl = new_table(libref, name)
            tbl.meta_id = meta_id
            existing = tables.setdefault(tbl.id, tbl)
            if existing.meta_id is None:
                existing.meta_id = meta_id
            if role.lower() == "source":
                sources.append(existing)
            else:
                targets.append(existing)
        span_end = headers[i + 1][0] if i + 1 < len(headers) else len(code)
        steps.append(
            _Step(
                name=step_m.group(1),
                transform_type=(transform_m.group(1) if transform_m else ""),
                sources=sources,
                targets=targets,
                span=code[end:span_end],
            )
        )
    return steps


def _harvest_mapping(
    step: _Step,
    job_id: str,
    tables: dict[str, Table],
    columns: dict[str, Column],
    column_edges: list[LineageChain],
    flags: list[Flag],
) -> None:
    output_tables = {
        m.group(1): m.group(2).strip()
        for m in _LET_OUTPUT_TABLE.finditer(step.span)
    }
    cols: dict[tuple[str, str], dict[str, str]] = {}
    for m in _LET_OUTPUT_COL.finditer(step.span):
        n, col_n, prop, value = m.groups()
        cols.setdefault((n, col_n), {})[prop.lower()] = value.strip()

    for (n, _), props in sorted(cols.items()):
        name = props.get("name")
        if not name:
            continue
        target_ref = props.get("table") or output_tables.get(n)
        if not target_ref:
            continue
        target = _resolve_table(target_ref, tables)
        target_col = new_column(target.id, name)
        target_col.data_type = _SAS_TYPE.get(props.get("type", ""), "UNKNOWN")
        columns.setdefault(target_col.id, target_col)

        inputs = _input_list(props)
        exp = props.get("exp", "")
        if not inputs:
            continue

        def _emit(src_table: Table, source_name: str, ev: Evidence) -> None:
            src_col = new_column(src_table.id, source_name)
            columns.setdefault(src_col.id, src_col)
            column_edges.append(
                LineageChain(
                    id=lineage_chain_id(target_col.id, src_col.id, 1),
                    mart_column_id=target_col.id,
                    source_column_id=src_col.id,
                    chain_order=1,
                    job_id=job_id,
                    step_name=step.name,
                    step_type=StepType.OTHER,
                    transformation_logic=exp,
                    evidence=ev,
                )
            )

        if len(step.sources) == 1:
            for source_name in inputs:
                _emit(step.sources[0], source_name, Evidence.METADATA_MACRO)
            continue

        # Ambiguous mapping: the input names no table. Fall back to the
        # generated SQL in this step's span, where aliases qualify refs.
        alias_map = _sql_alias_map(step.span, step.sources)
        qrefs = qualified_column_refs(step.span)
        unresolved = False
        for source_name in inputs:
            quals = qrefs.get(source_name.lower(), set())
            src_tables = {
                t.id: t
                for t in (alias_map[q] for q in quals if q in alias_map)
            }
            if len(src_tables) == 1:
                (src,) = src_tables.values()
                _emit(src, source_name, Evidence.PARSED_SQL)
            else:
                unresolved = True
        if unresolved:
            flags.append(
                Flag(
                    ref_id=f"{job_id}.{step.name}.{name}",
                    reason=UnmappableReason.MULTI_SOURCE,
                    context=(
                        f"{len(step.sources)} source tables; mapping "
                        "input is unqualified and generated SQL did "
                        "not disambiguate"
                    ),
                    snippet=exp[:200],
                )
            )


def _sql_alias_map(span: str, sources: list[Table]) -> dict[str, Table]:
    """Map SQL aliases (and bare table names) to header source tables.

    Only tables the header declared as sources participate — a resolved
    alias pointing anywhere else is not an attribution we can trust.
    """
    by_id = {t.id: t for t in sources}
    alias_map: dict[str, Table] = {}
    for libref, table, alias in extract_sql_tables(span):
        if table.startswith("&") or libref == "__UNPARSEABLE__":
            continue
        tid = make_table_id(libref or "WORK", table)
        src = by_id.get(tid)
        if src is None:
            continue
        alias_map[table.lower()] = src
        if alias:
            alias_map[alias.lower()] = src
    return alias_map


def _resolve_table(ref: str, tables: dict[str, Table]) -> Table:
    libref, _, name = ref.rpartition(".")
    tbl = new_table(libref or "WORK", name)
    return tables.setdefault(tbl.id, tbl)


def _input_list(props: dict[str, str]) -> list[str]:
    try:
        count = int(props.get("input_count", "1"))
    except ValueError:
        count = 1
    if count > 1:
        numbered = [
            props[f"input{i}"]
            for i in range(1, count + 1)
            if f"input{i}" in props
        ]
        if numbered:
            return numbered
    single = props.get("input")
    return [single] if single else []

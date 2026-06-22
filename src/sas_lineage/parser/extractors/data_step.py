"""
DATA step extractor.

Identifies output dataset, source datasets (SET/MERGE/MODIFY/UPDATE),
and captures assignment/CASE expressions as transformation logic.

Hard cases flagged (not dropped):
  - Unresolved macros in dataset names -> macro_unresolved
  - Dynamic column names (&var-based output) -> dynamic_column_name
  - Hand-written logic with no clear attribution -> hand_written_code
"""

from __future__ import annotations

import re

from sas_lineage.ids import lineage_chain_id as make_lc_id
from sas_lineage.models import (
    Column,
    Flag,
    LineageChain,
    StepType,
    Table,
    UnmappableReason,
)
from sas_lineage.parser import patterns
from sas_lineage.parser.extractors._factory import (
    flag_macro,
    new_column,
    new_table,
)
from sas_lineage.parser.log_resolver import LogResolver

# First tokens that mean a line is a statement, not a column assignment.
_NON_ASSIGN = {
    "if",
    "then",
    "else",
    "do",
    "end",
    "by",
    "set",
    "merge",
    "modify",
    "update",
    "where",
    "retain",
    "format",
    "length",
    "label",
    "keep",
    "drop",
    "rename",
    "array",
    "call",
    "put",
    "output",
    "run",
    "data",
    "attrib",
    "informat",
    "when",
    "select",
    "otherwise",
    "stop",
    "return",
}

# SAS functions/keywords that BARE_IDENT leaks as if they were source
# columns. Filtered out before building lineage edges (F4).
_NON_REF = frozenset(
    {
        "case",
        "when",
        "then",
        "else",
        "end",
        "and",
        "or",
        "not",
        "in",
        "like",
        "intnx",
        "intck",
        "input",
        "put",
        "today",
        "datepart",
        "mdy",
        "year",
        "month",
        "day",
        "sum",
        "mean",
        "min",
        "max",
        "coalesce",
    }
)

# Strip string literals ('...'/"...") so words inside them aren't read as
# columns; then strip format/informat refs (BEST12., $CHAR10.).
# Doubled-quote escapes inside strings ('it''s', "he""said") are valid SAS;
# the inner '' / "" must not end the match early (F-str-escape).
_STR_LITERAL = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
_FORMAT_REF = re.compile(r"\$?[A-Za-z]\w*\d*\.\d*")

# SET/MERGE clause parsing (F9): drop dataset options, then read each
# whitespace-separated `[libref.]dataset` token so all sources are captured.
# One-level nesting supports where=(x>0) style dataset options.
_DS_OPTION = re.compile(r"\((?:[^()]*|\([^()]*\))*\)")
# libref capped at 8 chars (SAS limit); dataset name unbounded (&macro ok).
_DS_REF = re.compile(r"(?:([A-Za-z]\w{0,7})\.)?(&?\w+)")


class DataStepExtractor:
    """Extracts column-level lineage from a DATA step block."""

    def can_extract(self, code_block: str) -> bool:
        return bool(patterns.DATA_STMT.search(code_block))

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        tables: list[Table] = []
        columns: list[Column] = []
        lineage: list[LineageChain] = []
        flags: list[Flag] = []

        # DATA _null_ produces no dataset: nothing to attribute.
        if patterns.DATA_NULL.search(code_block):
            return tables, columns, lineage, flags

        output_libref, output_dsn = _parse_data_target(
            code_block, resolver, flags, step_name
        )
        if not output_dsn:
            return tables, columns, lineage, flags

        out_table = new_table(output_libref or "WORK", output_dsn)
        out_tid = out_table.id
        tables.append(out_table)

        sources = _parse_sources(code_block, resolver, flags, step_name)
        source_tids: list[str] = []
        for src_libref, src_dsn in sources:
            src_table = new_table(src_libref or "WORK", src_dsn)
            source_tids.append(src_table.id)
            tables.append(src_table)

        if not sources:
            flags.append(
                Flag(
                    ref_id=f"{job_id}.{step_name}",
                    reason=UnmappableReason.HAND_WRITTEN_CODE,
                    context=(
                        f"DATA step {output_dsn} has no SET/MERGE/MODIFY"
                    ),
                    snippet=code_block[:200],
                )
            )
        elif len(source_tids) > 1:
            n = len(source_tids)
            flags.append(
                Flag(
                    ref_id=f"{job_id}.{step_name}",
                    reason=UnmappableReason.MULTI_SOURCE,
                    context=(
                        f"DATA step {output_dsn} MERGEs {n} sources; "
                        "per-column upstream unresolved"
                    ),
                    snippet=code_block[:200],
                )
            )

        # Single source = unambiguous attribution; otherwise capture the
        # transformed column but leave its upstream unresolved (partial).
        src_tid = source_tids[0] if len(source_tids) == 1 else None
        _extract_assignments(
            code_block,
            out_tid,
            src_tid,
            resolver,
            job_id,
            step_name,
            columns,
            lineage,
            flags,
        )

        return tables, columns, lineage, flags


def _parse_data_target(
    code: str,
    resolver: LogResolver,
    flags: list[Flag],
    step_name: str,
) -> tuple[str | None, str | None]:
    m = patterns.DATA_TARGET.search(code)
    if not m:
        return None, None

    if m.group(1) and m.group(2):
        libref, dsn = m.group(1), m.group(2)
    elif m.group(3):
        libref, dsn = None, m.group(3)
    else:
        return None, None

    raw_dsn = dsn
    if "&" in raw_dsn:
        dsn, ok = resolver.resolve(raw_dsn)
        if not ok:
            flags.append(
                Flag(
                    ref_id=step_name,
                    reason=UnmappableReason.MACRO_UNRESOLVED,
                    context=f"DATA target has unresolved macro: {raw_dsn}",
                    snippet=raw_dsn,
                )
            )
    return libref, dsn.upper() if dsn else None


def _parse_sources(
    code: str,
    resolver: LogResolver,
    flags: list[Flag],
    step_name: str,
) -> list[tuple[str | None, str]]:
    sources: list[tuple[str | None, str]] = []
    for m in patterns.SET_STMT.finditer(code):
        body = _DS_OPTION.sub(" ", m.group(2))
        for tok in body.split():
            # ponytail: drops dataset options written `end = eof` (spaced);
            # the no-space `end=eof` form, the common one, is skipped here.
            if "=" in tok:
                continue
            ref = _DS_REF.fullmatch(tok)
            if not ref:
                continue
            libref, dsn = ref.group(1), ref.group(2)

            if "&" in dsn:
                resolved, ok = resolver.resolve(dsn)
                if not ok:
                    flags.append(
                        Flag(
                            ref_id=step_name,
                            reason=UnmappableReason.MACRO_UNRESOLVED,
                            context=f"SET source unresolved: {dsn}",
                            snippet=dsn,
                        )
                    )
                dsn = resolved

            sources.append((libref, dsn.upper()))
    return sources


def _extract_assignments(
    code: str,
    out_tid: str,
    src_tid: str | None,
    resolver: LogResolver,
    job_id: str,
    step_name: str,
    columns: list[Column],
    lineage: list[LineageChain],
    flags: list[Flag],
) -> None:
    for m in patterns.DATA_ASSIGN.finditer(code):
        lhs = m.group(1)
        if lhs.lower() in _NON_ASSIGN:
            continue
        rhs = m.group(2).strip()
        out_name = lhs.upper()
        out_col = new_column(out_tid, out_name)
        columns.append(out_col)

        if "&" in rhs:
            flag_macro(
                rhs, resolver, f"{job_id}.{step_name}.{out_name}", flags
            )

        if src_tid is None:
            continue

        cleaned = _STR_LITERAL.sub(" ", rhs)
        cleaned = _FORMAT_REF.sub(" ", cleaned)
        refs = [
            r.upper()
            for r in patterns.BARE_IDENT.findall(cleaned)
            if r.upper() != out_name and r.lower() not in _NON_REF
        ]
        for ref in dict.fromkeys(refs):
            src_col = new_column(src_tid, ref)
            columns.append(src_col)
            lineage.append(
                LineageChain(
                    id=make_lc_id(out_col.id, src_col.id, 1),
                    mart_column_id=out_col.id,
                    source_column_id=src_col.id,
                    chain_order=1,
                    job_id=job_id,
                    step_name=step_name,
                    step_type=StepType.DATA,
                    transformation_logic=rhs,
                )
            )

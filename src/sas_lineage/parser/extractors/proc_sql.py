"""
PROC SQL extractor.

Handles CREATE TABLE ... AS SELECT patterns. Emits the output table, source
tables, the output columns (one per SELECT-list item), the source columns they
derive from, and a column-level lineage edge per derivation carrying the
verbatim expression as transformation_logic.

Unresolvable items (macros in the target or an expression) are flagged, never
dropped. `SELECT *` is left to schema enrichment downstream. No columns are
invented.
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
from sas_lineage.parser.sql_tokeniser import extract_sql_tables, scan_tokens


def _split_top_level(select_list: str) -> list[str]:
    """Split a SELECT list on depth-0 commas, ignoring those in strings."""
    items: list[str] = []
    last = 0
    for t in scan_tokens(select_list):
        if t.kind == "comma" and t.depth == 0:
            items.append(select_list[last : t.start])
            last = t.end
    items.append(select_list[last:])
    return [i.strip() for i in items if i.strip()]


def _split_select_from(rest: str) -> tuple[str, str]:
    """Split ``<select-list> from <from-clause>`` at the depth-0 FROM.

    ``rest`` begins just after ``... as select``. Stops at the depth-0 ``;``
    that ends the statement. A select with no FROM yields an empty clause.
    """
    end = len(rest)
    from_pos = None
    for t in scan_tokens(rest):
        if t.depth == 0 and t.kind == "semi":
            end = t.start
            break
        if (
            t.depth == 0
            and t.kind == "ident"
            and t.value == "from"
            and from_pos is None
        ):
            from_pos = t.start
    if from_pos is None:
        return rest[:end], ""
    return rest[:from_pos], rest[from_pos:end]


class ProcSqlExtractor:
    """Extracts column-level lineage from PROC SQL CREATE TABLE statements."""

    def can_extract(self, code_block: str) -> bool:
        return bool(patterns.PROC_SQL.search(code_block))

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

        for m in patterns.SQL_CREATE_TABLE.finditer(code_block):
            libref = (m.group(1) or "WORK").upper()
            tables.append(new_table(libref, m.group(2).upper()))

        for mm in re.finditer(
            r"\bcreate\s+table\s+(&\w+)", code_block, re.IGNORECASE
        ):
            flags.append(
                Flag(
                    ref_id=f"{job_id}.{step_name}",
                    reason=UnmappableReason.MACRO_UNRESOLVED,
                    context=f"CREATE TABLE target is macro {mm.group(1)}",
                    snippet=mm.group(0),
                )
            )

        for stmt in patterns.SQL_CREATE_AS_SELECT.finditer(code_block):
            out_libref = (stmt.group(1) or "WORK").upper()
            out_dsn = stmt.group(2).upper()
            out_table = new_table(out_libref, out_dsn)
            tables.append(out_table)

            select_list, from_clause = _split_select_from(
                code_block[stmt.end() :]
            )
            aliases = self._build_sources(
                select_list + from_clause,
                resolver,
                f"{job_id}.{step_name}",
                tables,
                flags,
            )
            self._extract_select(
                select_list,
                out_table,
                aliases,
                resolver,
                job_id,
                step_name,
                tables,
                columns,
                lineage,
                flags,
            )

        return tables, columns, lineage, flags

    def _build_sources(
        self,
        buffer: str,
        resolver: LogResolver,
        ref_id: str,
        tables: list[Table],
        flags: list[Flag],
    ) -> dict[str, tuple[str, str]]:
        """Emit source tables; map each table name + alias to (libref, name).

        A macro-named source resolves via the log; unresolved ones are
        flagged and contribute no table (F6, flag-never-drop).
        """
        aliases: dict[str, tuple[str, str]] = {}
        had_unresolved = False
        for libref, table, alias in extract_sql_tables(buffer):
            # Three-part dotted ref (e.g. A.B.C) is unparseable; flag it.
            if libref == "__UNPARSEABLE__":
                flags.append(
                    Flag(
                        ref_id=ref_id,
                        reason=UnmappableReason.MACRO_UNRESOLVED,
                        context=(
                            f"Unparseable three-part table ref: {table!r}"
                        ),
                        snippet=table,
                    )
                )
                continue
            if table.startswith("&"):
                resolved, ok = resolver.resolve(table)
                if not ok:
                    flag_macro(table, resolver, ref_id, flags)
                    had_unresolved = True
                    continue
                lib, _, name = resolved.upper().partition(".")
                if not name:
                    lib, name = "WORK", lib
            else:
                lib = (libref or "WORK").upper()
                name = table.upper()
            tables.append(new_table(lib, name))
            aliases[name] = (lib, name)
            if alias:
                aliases[alias.upper()] = (lib, name)
        # An unresolved macro source alongside resolved ones means column
        # attribution via aliases is partial; flag it so nothing is silently
        # mis-attributed (flag-never-drop).
        if had_unresolved and aliases:
            flags.append(
                Flag(
                    ref_id=ref_id,
                    reason=UnmappableReason.MULTI_SOURCE,
                    context=(
                        "Unresolved macro source alongside resolved sources;"
                        " column attribution is partial/suspect"
                    ),
                    snippet=buffer[:200],
                )
            )
        return aliases

    def _extract_select(
        self,
        select_list: str,
        out_table: Table,
        aliases: dict[str, tuple[str, str]],
        resolver: LogResolver,
        job_id: str,
        step_name: str,
        tables: list[Table],
        columns: list[Column],
        lineage: list[LineageChain],
        flags: list[Flag],
    ) -> None:
        for item in _split_top_level(select_list):
            if item == "*" or item.endswith(".*"):
                continue

            alias_match = patterns.SQL_ITEM_ALIAS.search(item)
            if alias_match:
                out_name = alias_match.group(1).upper()
                expr = item[: alias_match.start()].strip()
            else:
                expr = item
                qual = patterns.SQL_QUALIFIED_COL.search(item)
                out_name = (qual.group(2) if qual else item).upper()

            out_col = new_column(out_table.id, out_name)
            columns.append(out_col)

            if "&" in expr:
                flag_macro(
                    expr,
                    resolver,
                    f"{job_id}.{step_name}.{out_name}",
                    flags,
                )

            sources = self._source_columns(
                expr,
                aliases,
                tables,
                columns,
                flags,
                f"{job_id}.{step_name}.{out_name}",
            )
            for src_col in sources:
                lineage.append(
                    LineageChain(
                        id=make_lc_id(out_col.id, src_col.id, 1),
                        mart_column_id=out_col.id,
                        source_column_id=src_col.id,
                        chain_order=1,
                        job_id=job_id,
                        step_name=step_name,
                        step_type=StepType.PROC_SQL,
                        transformation_logic=expr,
                    )
                )

    def _source_columns(
        self,
        expr: str,
        aliases: dict[str, tuple[str, str]],
        tables: list[Table],
        columns: list[Column],
        flags: list[Flag],
        ref_id: str,
    ) -> list[Column]:
        found: list[Column] = []
        qualified = list(
            dict.fromkeys(patterns.SQL_QUALIFIED_COL.findall(expr))
        )
        if qualified:
            for alias, col in qualified:
                libref, name = aliases.get(
                    alias.upper(), ("WORK", alias.upper())
                )
                tbl = new_table(libref, name)
                tables.append(tbl)
                src_col = new_column(tbl.id, col.upper())
                columns.append(src_col)
                found.append(src_col)
        elif len(aliases) == 1 and expr.isidentifier():
            ((libref, name),) = set(aliases.values())
            tbl = new_table(libref, name)
            tables.append(tbl)
            src_col = new_column(tbl.id, expr.upper())
            columns.append(src_col)
            found.append(src_col)
        elif expr.isidentifier() and len(set(aliases.values())) > 1:
            n = len(set(aliases.values()))
            flags.append(
                Flag(
                    ref_id=ref_id,
                    reason=UnmappableReason.MULTI_SOURCE,
                    context=f"unqualified column {expr} in {n}-table join",
                    snippet=expr,
                )
            )
        return found

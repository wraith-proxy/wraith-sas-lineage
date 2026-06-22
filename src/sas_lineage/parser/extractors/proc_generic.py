"""
Generic PROC extractor: everything that is not PROC SQL.

PROC SORT/FORMAT/TRANSPOSE/SUMMARY etc. are not column-traced, but they must
not be silently dropped (flag-never-drop). Captures the input (data=) and
output (out=) datasets at table level; flags the column gap for any PROC other
than SORT (a pure reorder that preserves columns unchanged).
"""

from __future__ import annotations

from sas_lineage.models import (
    Column,
    Flag,
    LineageChain,
    Table,
    UnmappableReason,
)
from sas_lineage.parser import patterns
from sas_lineage.parser.extractors._factory import new_table
from sas_lineage.parser.log_resolver import LogResolver


class GenericProcExtractor:
    """Captures non-SQL PROC steps at table level; flags untraced columns."""

    def can_extract(self, code_block: str) -> bool:
        m = patterns.PROC_STMT.search(code_block)
        return bool(m) and m.group(1).lower() != "sql"

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        m = patterns.PROC_STMT.search(code_block)
        if m is None:
            return [], [], [], []
        ptype = m.group(1).upper()

        tables: list[Table] = []
        for pat in (patterns.PROC_DATA_ARG, patterns.PROC_OUT_ARG):
            m = pat.search(code_block)
            if m:
                tables.append(
                    new_table(
                        (m.group(1) or "WORK").upper(), m.group(2).upper()
                    )
                )

        flags: list[Flag] = []
        out = patterns.PROC_OUT_ARG.search(code_block)
        if out and ptype != "SORT":
            dsn = out.group(2).upper()
            flags.append(
                Flag(
                    ref_id=f"{job_id}.{step_name}",
                    reason=UnmappableReason.HAND_WRITTEN_CODE,
                    context=f"PROC {ptype} output {dsn} not column-traced",
                    snippet=code_block[:200],
                )
            )

        return tables, [], [], flags

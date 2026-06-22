"""
RSUBMIT extractor.

Tags remote execution blocks. Per the plan we *parse the contents* (so remote
lineage is not lost) but mark the execution context: every table discovered
inside the block is flagged is_remote, and a remote_execution flag is raised.
"""

from __future__ import annotations

from dataclasses import replace

from sas_lineage.models import (
    Column,
    Flag,
    LineageChain,
    Table,
    UnmappableReason,
)
from sas_lineage.parser import patterns
from sas_lineage.parser.log_resolver import LogResolver


class RsubmitExtractor:
    """Detects RSUBMIT blocks, parses inner steps, tags them remote."""

    def can_extract(self, code_block: str) -> bool:
        return bool(patterns.RSUBMIT_START.search(code_block))

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        # Imported here to avoid a module-level cycle with the builder.
        from sas_lineage.parser.builder import _split_into_blocks
        from sas_lineage.parser.extractors.data_step import DataStepExtractor
        from sas_lineage.parser.extractors.proc_sql import ProcSqlExtractor

        # Server name: explicit RSUBMIT <server>, else the SIGNON that
        # established the session (remote=<server>).
        server = "UNKNOWN"
        m = patterns.RSUBMIT_SERVER.search(
            code_block
        ) or patterns.SIGNON_REMOTE.search(code_block)
        if m:
            server, _ = resolver.resolve(m.group(1))
            server = server.upper()

        has_signon = bool(
            patterns.SIGNON_STMT.search(code_block)
            or patterns.SIGNOFF_STMT.search(code_block)
        )
        session = " (explicit signon/off)" if has_signon else ""

        inner = _extract_inner(code_block)

        tables: list[Table] = []
        columns: list[Column] = []
        lineage: list[LineageChain] = []
        flags: list[Flag] = [
            Flag(
                ref_id=f"{job_id}.{step_name}",
                reason=UnmappableReason.REMOTE_EXECUTION,
                context=(
                    f"RSUBMIT to {server}{session}: parsed, executes remotely"
                ),
                snippet=inner[:300],
            )
        ]

        inner_extractors = (DataStepExtractor(), ProcSqlExtractor())
        for inner_name, block in _split_into_blocks(inner):
            for ex in inner_extractors:
                if ex.can_extract(block):
                    t, c, lc, f = ex.extract(
                        block, resolver, job_id, f"{step_name}.{inner_name}"
                    )
                    tables.extend(replace(tbl, is_remote=True) for tbl in t)
                    columns.extend(c)
                    lineage.extend(lc)
                    flags.extend(f)

        return tables, columns, lineage, flags


def _extract_inner(code_block: str) -> str:
    """Return the body between RSUBMIT and ENDRSUBMIT.

    Drops the `rsubmit <server>;` statement itself so the body starts at the
    first real step. Otherwise a single-line block would hide the inner step
    behind the server token.
    """
    start = patterns.RSUBMIT_START.search(code_block)
    end = patterns.RSUBMIT_END.search(code_block)
    if start and end and end.start() > start.end():
        inner = code_block[start.end() : end.start()]
        semi = inner.find(";")
        if semi != -1:
            inner = inner[semi + 1 :]
        return inner.strip()
    return code_block

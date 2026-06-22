"""
Unknown-macro-call extractor.

A user macro call (%load_risk(...)) can hide an entire transform the parser
cannot see into. SCD2 calls are handled by the SCD2 extractor; SAS
macro-language statements (%let, %if, %do, ...) and common utility functions
are control flow, not lineage. Everything else is flagged for human review
rather than silently dropped.
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
from sas_lineage.parser.log_resolver import LogResolver

# SAS macro-language statements and stock functions: control flow / utility,
# never a data transform, so never flagged.
_MACRO_BUILTINS = {
    "let",
    "put",
    "do",
    "end",
    "mend",
    "macro",
    "if",
    "then",
    "else",
    "global",
    "local",
    "return",
    "goto",
    "abort",
    "include",
    "inc",
    "list",
    "run",
    "window",
    "display",
    "sysrput",
    "syslput",
    "symput",
    "symget",
    "sysfunc",
    "sysevalf",
    "eval",
    "str",
    "nrstr",
    "bquote",
    "nrbquote",
    "superq",
    "unquote",
    "scan",
    "qscan",
    "substr",
    "upcase",
    "lowcase",
    "index",
    "length",
    "trim",
    "left",
    "sysget",
    "syscall",
}


class MacroCallExtractor:
    """Flags macro invocations that are neither SCD2 nor SAS built-ins."""

    def can_extract(self, code_block: str) -> bool:
        return bool(patterns.MACRO_CALL.search(code_block))

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        flags: list[Flag] = []
        seen: set[str] = set()
        for m in patterns.MACRO_CALL.finditer(code_block):
            name = m.group(1)
            low = name.lower()
            if low in _MACRO_BUILTINS or low in seen:
                continue
            if patterns.SCD2_MACRO.match(m.group(0)):
                continue
            seen.add(low)
            flags.append(
                Flag(
                    ref_id=f"{job_id}.{step_name}",
                    reason=UnmappableReason.HAND_WRITTEN_CODE,
                    context=f"unrecognised macro %{name}: lineage not traced",
                    snippet=code_block[m.start() : m.start() + 200],
                )
            )
        return [], [], [], flags

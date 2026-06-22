"""
SCD Type 2 extractor.

DI Studio generates SCD2 loader macro calls (%di_scd2_load(...)). The internal
column mapping is opaque from code alone, so we capture it as a known transform
type: emit the source/target tables found in the macro arguments, and raise a
flag so a human confirms the column-level detail.
"""

from __future__ import annotations

import re

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

_SOURCE_KEYS = {"in", "source", "base", "intable", "src", "source_table"}
_TARGET_KEYS = {"out", "target", "dim", "outtable", "dim_table", "table"}
_KWARG = re.compile(r"(\w+)\s*=\s*(?:([A-Za-z]\w{0,7})\.)?(\w+)")


class Scd2Extractor:
    """Detects DI Studio SCD Type 2 macro blocks."""

    def can_extract(self, code_block: str) -> bool:
        return bool(patterns.SCD2_MACRO.search(code_block))

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        tables: list[Table] = []
        for key, libref, name in _KWARG.findall(code_block):
            kl = key.lower()
            if kl in _SOURCE_KEYS or kl in _TARGET_KEYS:
                tables.append(
                    new_table((libref or "WORK").upper(), name.upper())
                )

        flags = [
            Flag(
                ref_id=f"{job_id}.{step_name}",
                reason=UnmappableReason.HAND_WRITTEN_CODE,
                context="SCD2 macro: columns not traced, confirm manually",
                snippet=code_block[:200],
            )
        ]
        return tables, [], [], flags

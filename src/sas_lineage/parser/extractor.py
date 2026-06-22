"""
StepExtractor Protocol: the interface all extractors must satisfy.

Each extractor handles one step type (DATA, PROC SQL, RSUBMIT, etc.)
and converts a raw code block + optional log block into typed model objects.
"""

from __future__ import annotations

from typing import Protocol

from sas_lineage.models import Column, Flag, LineageChain, Table
from sas_lineage.parser.log_resolver import LogResolver


class StepExtractor(Protocol):
    """Interface for all step-type extractors."""

    def can_extract(self, code_block: str) -> bool:
        """Return True if this extractor handles the given code block."""
        ...

    def extract(
        self,
        code_block: str,
        resolver: LogResolver,
        job_id: str,
        step_name: str,
    ) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]:
        """
        Parse code_block and return discovered entities.

        Tables and Columns emitted here are incomplete candidates;
        the builder deduplicates and links them into the Provenance.
        """
        ...

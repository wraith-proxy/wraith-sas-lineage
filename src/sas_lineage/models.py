"""Canonical data model: mirrors provenance.json and the Turso schema."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class Layer(StrEnum):
    """Data layer classification for SAS tables."""

    RAW = "RAW"
    ODS = "ODS"
    STG = "STG"
    MART = "MART"


class StepType(StrEnum):
    """SAS step type that produced a lineage hop."""

    DATA = "DATA"
    PROC_SQL = "PROC_SQL"
    PROC_FORMAT = "PROC_FORMAT"
    PROC_SORT = "PROC_SORT"
    SCD2 = "SCD2"
    RSUBMIT = "RSUBMIT"
    OTHER = "OTHER"


class UnmappableReason(StrEnum):
    """Reason a column or step could not be fully resolved."""

    MACRO_UNRESOLVED = "macro_unresolved"
    DYNAMIC_COLUMN_NAME = "dynamic_column_name"
    HAND_WRITTEN_CODE = "hand_written_code"
    REMOTE_EXECUTION = "remote_execution"
    STEP_COUNT_MISMATCH = "step_count_mismatch"
    MULTI_SOURCE = "multi_source"


class Evidence(StrEnum):
    """Where a lineage edge was derived from."""

    METADATA_MACRO = "metadata_macro"
    PARSED_SQL = "parsed_sql"
    LOG_CONFIRMED = "log_confirmed"


class Frequency(StrEnum):
    """Inferred run cadence for a SAS job."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


@dataclass
class Table:
    """A SAS dataset (libref.name) discovered during parsing."""

    id: str
    name: str
    libref: str
    engine: str
    path: str
    layer: Layer
    is_remote: bool
    meta_id: str | None = None
    is_intermediate: bool = False


@dataclass
class Column:
    """A column within a discovered SAS table."""

    id: str
    table_id: str
    name: str
    layer: Layer
    data_type: str
    nullable: bool


@dataclass
class Job:
    """A SAS program (file stem) processed by the parser."""

    id: str
    name: str
    flow_id: str | None
    frequency: Frequency | None
    frequency_evidence: list[str] = field(default_factory=list)
    owner: str | None = None
    domain: str | None = None


@dataclass
class LineageChain:
    """One hop in the column-level lineage chain from source to MART."""

    id: str
    mart_column_id: str
    source_column_id: str
    chain_order: int
    job_id: str
    step_name: str
    step_type: StepType
    transformation_logic: str
    data_type_at_step: str | None = None
    nullable_at_step: bool | None = None
    unmappable_reason: UnmappableReason | None = None
    evidence: Evidence | None = None


@dataclass
class TableLineage:
    """A table-level edge (source table → target table) within one step.

    Carries DI-header and SYSLAST derived flow so user-written steps with
    no column mapping still contribute lineage.
    """

    id: str
    source_table_id: str
    target_table_id: str
    job_id: str
    step_name: str
    transform_type: str
    evidence: Evidence | None = None


@dataclass
class QualityRule:
    """A data quality check extracted from a SAS job."""

    id: str
    job_id: str
    rule_name: str
    rule_definition: str
    applies_to_column_id: str | None = None


@dataclass
class Flag:
    """An item that could not be fully parsed and needs human review."""

    ref_id: str
    reason: UnmappableReason
    context: str
    snippet: str


@dataclass
class ReconciliationResult:
    """Summary of parser output vs Excel mapping reconciliation."""

    excel_supplied: bool = False
    matches: int = 0
    mismatches: list[str] = field(default_factory=list)
    parser_only: list[str] = field(default_factory=list)
    excel_only: list[str] = field(default_factory=list)


@dataclass
class ProvenanceMeta:
    """Metadata header written into every provenance.json output."""

    generated_at: str
    parser_version: str
    estate: str
    job_count: int
    flow_count: int


@dataclass
class Provenance:
    """Root container for all lineage data emitted by the parser."""

    meta: ProvenanceMeta
    tables: list[Table] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)
    lineage_chain: list[LineageChain] = field(default_factory=list)
    table_lineage: list[TableLineage] = field(default_factory=list)
    quality_rules: list[QualityRule] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)
    reconciliation: ReconciliationResult = field(
        default_factory=ReconciliationResult
    )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

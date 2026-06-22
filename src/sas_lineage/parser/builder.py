"""
ProvenanceBuilder: orchestrates Walker + extractors → Provenance.

Usage:
    builder = ProvenanceBuilder(code_dir, log_dir, estate="acme-risk")
    provenance = builder.build()
    provenance.to_json()
"""

from __future__ import annotations

import datetime
from pathlib import Path

from sas_lineage import __version__
from sas_lineage.ids import (
    job_id as make_job_id,
)
from sas_lineage.ids import (
    lineage_chain_id as make_lc_id,
)
from sas_lineage.models import (
    Column,
    Flag,
    Job,
    LineageChain,
    Provenance,
    ProvenanceMeta,
    QualityRule,
    ReconciliationResult,
    Table,
    UnmappableReason,
)
from sas_lineage.parser import patterns
from sas_lineage.parser.extractor import StepExtractor
from sas_lineage.parser.log_resolver import LogResolver
from sas_lineage.parser.walker import walk_pairs


class ProvenanceBuilder:
    """Orchestrate extractors over a SAS code dir into a Provenance."""

    def __init__(
        self,
        code_dir: Path,
        log_dir: Path,
        estate: str,
    ) -> None:
        self.code_dir = code_dir
        self.log_dir = log_dir
        self.estate = estate
        self._extractors: list[StepExtractor] = []

        self._tables: dict[str, Table] = {}
        self._columns: dict[str, Column] = {}
        self._jobs: dict[str, Job] = {}
        self._edges: list[LineageChain] = []
        self._quality_rules: list[QualityRule] = []
        self._flags: list[Flag] = []

    def register(self, extractor: StepExtractor) -> None:
        self._extractors.append(extractor)

    def build(self) -> Provenance:
        flow_ids: set[str] = set()

        for pair in walk_pairs(self.code_dir, self.log_dir):
            code = pair.code_path.read_text(errors="replace")
            resolver = LogResolver(pair.log_path)
            resolver.load_code_macros(code)
            job = self._build_job(pair.name, code, resolver)
            self._jobs[job.id] = job
            if job.flow_id:
                flow_ids.add(job.flow_id)
            self._extract_from_job(code, resolver, job.id)
            self._check_step_count(job.id, code, resolver)

        self._resolve_librefs()

        return Provenance(
            meta=ProvenanceMeta(
                generated_at=datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                parser_version=__version__,
                estate=self.estate,
                job_count=len(self._jobs),
                flow_count=len(flow_ids),
            ),
            tables=list(self._tables.values()),
            columns=list(self._columns.values()),
            jobs=list(self._jobs.values()),
            lineage_chain=_stitch_chains(self._edges),
            quality_rules=self._quality_rules,
            flags=self._flags,
            reconciliation=ReconciliationResult(),
        )

    def _resolve_librefs(self) -> None:
        """
        LibnameExtractor emits one library row per libref (name == libref)
        carrying engine/path/layer/is_remote. Push those onto the datasets that
        share the libref, propagate layer to their columns, then drop the
        library rows. They are not datasets and have no home in `tables`.
        """
        libdefs = {
            t.libref: t for t in self._tables.values() if t.name == t.libref
        }
        for t in self._tables.values():
            if t.name == t.libref:
                continue
            lib = libdefs.get(t.libref)
            if lib:
                t.engine = lib.engine
                t.path = lib.path
                t.layer = lib.layer
                t.is_remote = lib.is_remote

        table_layer = {
            t.id: t.layer for t in self._tables.values() if t.name != t.libref
        }
        for c in self._columns.values():
            if c.table_id in table_layer:
                c.layer = table_layer[c.table_id]

        self._tables = {
            tid: t for tid, t in self._tables.items() if t.name != t.libref
        }

    def _build_job(self, name: str, code: str, resolver: LogResolver) -> Job:
        from sas_lineage.models import Frequency
        from sas_lineage.parser import freshness

        label, evidence = freshness.infer_from_name(name)
        log_label, log_evidence = freshness.infer_from_log_timestamps(
            resolver.run_timestamps()
        )
        evidence = evidence + log_evidence
        label = label or log_label

        return Job(
            id=make_job_id(name),
            name=name,
            flow_id=None,
            frequency=Frequency(label) if label else None,
            frequency_evidence=evidence,
        )

    def _check_step_count(
        self, job_id: str, code: str, resolver: LogResolver
    ) -> None:
        """Flag code-split steps that disagree with DATA/PROC log NOTEs."""
        log_steps = resolver.log_step_count()
        if not log_steps:
            return
        code_steps = sum(
            1
            for step_name, _ in _split_into_blocks(code)
            if not step_name.startswith("globals")
        )
        if code_steps != log_steps:
            self._flags.append(
                Flag(
                    ref_id=job_id,
                    reason=UnmappableReason.STEP_COUNT_MISMATCH,
                    context=(
                        f"parser split {code_steps} steps; "
                        f"log shows {log_steps}"
                    ),
                    snippet="",
                )
            )

    def _extract_from_job(
        self, code: str, resolver: LogResolver, job_id: str
    ) -> None:
        blocks = _split_into_blocks(code)
        for step_name, block in blocks:
            for extractor in self._extractors:
                if extractor.can_extract(block):
                    tables, columns, lineage, flags = extractor.extract(
                        block, resolver, job_id, step_name
                    )
                    for t in tables:
                        self._tables.setdefault(t.id, t)
                    for c in columns:
                        if c.data_type == "UNKNOWN":
                            logged = resolver.datatype(c.name)
                            if logged:
                                c.data_type = logged
                        self._columns.setdefault(c.id, c)
                    self._edges.extend(lineage)
                    self._flags.extend(flags)


def _stitch_chains(edges: list[LineageChain]) -> list[LineageChain]:
    """
    Turn per-step column edges into full provenance chains.

    Each edge is a single hop (source_column → immediate output column). A
    terminal column is produced by some step but never consumed as a source (a
    final MART column). From each terminal we walk upstream, emitting one row
    per hop with mart_column_id fixed to the terminal and chain_order as
    distance from it (1 = the hop producing the mart column).
    """
    producers: dict[str, list[LineageChain]] = {}
    sources: set[str] = set()
    for e in edges:
        producers.setdefault(e.mart_column_id, []).append(e)
        sources.add(e.source_column_id)

    terminals = set(producers) - sources
    chains: dict[str, LineageChain] = {}

    for terminal in terminals:
        seen: set[str] = set()
        stack: list[tuple[str, int]] = [(terminal, 1)]
        while stack:
            col, order = stack.pop()
            if col in seen:
                continue
            seen.add(col)
            for e in producers.get(col, []):
                cid = make_lc_id(terminal, e.source_column_id, order)
                chains[cid] = LineageChain(
                    id=cid,
                    mart_column_id=terminal,
                    source_column_id=e.source_column_id,
                    chain_order=order,
                    job_id=e.job_id,
                    step_name=e.step_name,
                    step_type=e.step_type,
                    transformation_logic=e.transformation_logic,
                    unmappable_reason=e.unmappable_reason,
                )
                stack.append((e.source_column_id, order + 1))

    return list(chains.values())


def _strip_comments(code: str) -> str:
    """Remove every SAS comment form before block splitting.

    /* ... */ (balanced and unterminated), %* ...; macro comments, and
    * ...; statement comments. Stripping these keeps starters/terminators
    from matching commented-out code.
    """
    clean = patterns.C_COMMENT_FULL.sub("", code)

    open_m = patterns.C_COMMENT_OPEN.search(clean)
    if open_m and not patterns.C_COMMENT_CLOSE.search(clean, open_m.end()):
        clean = clean[: open_m.start()]

    kept = [
        line
        for line in clean.splitlines(keepends=True)
        if not patterns.MACRO_COMMENT.match(line)
        and not patterns.STMT_COMMENT.match(line)
    ]
    return "".join(kept)


def _split_into_blocks(code: str) -> list[tuple[str, str]]:
    """
    Split SAS source into (step_name, block) pairs.

    DATA/PROC terminate at RUN/QUIT. RSUBMIT terminates at ENDRSUBMIT.
    %MACRO terminates at %MEND. Global statements (LIBNAME, %LET, OPTIONS)
    are collected into globals_N blocks so extractors still see them.
    """
    import re as _re

    clean = _strip_comments(code)

    _STARTERS = _re.compile(
        r"^\s*(?:data\s+\S|\bproc\s+\w+|\brsubmit\b|%macro\s+\w+)",
        _re.IGNORECASE | _re.MULTILINE,
    )
    _TERM_RUNQUIT = _re.compile(
        r"^\s*(?:run|quit)\s*;", _re.IGNORECASE | _re.MULTILINE
    )
    _TERM_ENDRSUBMIT = _re.compile(
        r"^\s*endrsubmit\s*;", _re.IGNORECASE | _re.MULTILINE
    )
    _TERM_MEND = _re.compile(
        r"^\s*%mend\b[^;]*;", _re.IGNORECASE | _re.MULTILINE
    )

    blocks: list[tuple[str, str]] = []
    pos = 0
    global_start = 0
    step_num = 0
    n = len(clean)

    while pos < n:
        m_start = _STARTERS.search(clean, pos)
        if m_start is None:
            tail = clean[pos:].strip()
            if tail:
                blocks.append((f"globals_{step_num}", clean[pos:]))
            break

        start_pos = m_start.start()
        globals_text = clean[global_start:start_pos].strip()
        if globals_text:
            blocks.append(
                (f"globals_{step_num}", clean[global_start:start_pos])
            )
            step_num += 1

        raw = m_start.group(0).strip().lower()
        if raw.startswith("data"):
            step_name = f"data_{step_num}"
            terminator = _TERM_RUNQUIT
        elif raw.startswith("rsubmit"):
            step_name = f"rsubmit_{step_num}"
            terminator = _TERM_ENDRSUBMIT
        elif raw.startswith("%macro"):
            m_mac = patterns.MACRO_DEF.match(raw)
            mac = m_mac.group(1) if m_mac else "anon"
            step_name = f"macro_{mac}_{step_num}"
            terminator = _TERM_MEND
        else:
            m_proc = _re.match(r"proc\s+(\w+)", raw, _re.IGNORECASE)
            ptype = m_proc.group(1).upper() if m_proc else "UNKNOWN"
            step_name = f"{ptype}_{step_num}"
            # PROC SQL ends with QUIT; other PROCs end with RUN; accept both
            terminator = _re.compile(
                r"^\s*(?:run|quit)\s*;", _re.IGNORECASE | _re.MULTILINE
            )

        m_end = terminator.search(clean, start_pos)
        if m_end is None:
            blocks.append((step_name, clean[start_pos:]))
            pos = n
            global_start = n
        else:
            end_pos = m_end.end()
            blocks.append((step_name, clean[start_pos:end_pos]))
            pos = end_pos
            global_start = end_pos
            step_num += 1

    return blocks or [("step_1", code)]

# 👻 SAS Lineage: Roadmap

Single source of truth: the spec, what is delivered, and what remains.
Supersedes `sas-lineage-scaffolding-plan.md` and `build-plan.md` (both
consolidated here).

**Status:** the three-tool pipeline emits real column-level provenance end to
end (sas-parse → sas-map → sas-ui), verified by `tests/test_end_to_end.py`
(186 passing, 96% coverage). Tool 1 and Tool 2 are feature-complete against the
spec; Tool 3 and cross-system inputs (flows) have known remaining scope. See
**Outstanding**.

---

## Purpose

One-time (re-runnable) adhoc extraction of full **column-level provenance**
from a deployed SAS DI Studio estate, to inform/generate a migration to dbt on
BigQuery.

## Design constraints

- **Estate:** large SAS DI Studio estates on Linux, with a live SAS Metadata
  Server.
- **Source of truth for parsing:** deployed `.sas` code **plus** full verbose
  execution logs (logs carry macro resolution, audit trails, datatypes).
- **Strategy:** parse code first, fill gaps from logs. Never modify jobs. No
  runtime instrumentation.
- **Layers:** RAW → ODS → STG → MART. De-normalised.
- **Scope:** trace everything. Every job, every column. Domain-agnostic.
- **Loss is acceptable iff flagged for human review.** Machine output is a
  guess; the source documents are truth.
- **Quality/Reconciliation rules:** clean parameters table, keyed by job name.
- **Freshness/SLA:** inferred from job name + log timestamps. Refinable.
- **Owner/domain:** supplied manually via an owners file.
- **Output contract standard:** Open Data Contract Standard (ODCS), consumed
  downstream by a modelgen tool that auto-generates dbt.

## System shape

```
.sas code + verbose logs
        |
   [Tool 1: SAS Parser]  --->  provenance.json  (the canonical artifact)
        |
   [Tool 2: Schema Mapper]  ---> ODCS contracts (YAML) + Turso DB load
        |  (+ params table, + manual owner/domain)
   [Tool 3: Web UI]  ---> local mkdocs-style app (markdown + mermaid)
        |
   modelgen ---> dbt models on BigQuery
```

JSON is the single seam. Tools 2 and 3 never read `.sas` or logs. IDs are
content-hashed so re-runs diff cleanly. Flag, never drop.

---

## Architecture (the contract)

### Tool 1: SAS Parser

Ingests `.sas` + logs, emits a single canonical `provenance.json` plus a
`parse_report.json` (counts, flag tallies, mismatches). Deterministic,
idempotent. A directory walker pairs each job's code with its log; pluggable
extractors (one per step type) emit typed model objects the builder
deduplicates and links.

### Tool 2: SAS Schema Mapper

Turns `provenance.json` into one ODCS contract per data product and loads the
Turso (SQLite) store. Inputs: `provenance.json`, a quality/reconciliation
params table (CSV, keyed by job name), manual owner/domain (CSV). Emits
contracts even when columns are flagged, carrying the flags through. Produces
`mapping_gaps.json`.

### Tool 3: Web UI

Local, boring, mkdocs-flavoured app over the Turso DB. SQLite query in, markdown
+ mermaid out. One flat query answers "full provenance of column X" via
`lineage_chain` ordered by `chain_order`. No graph traversal in the UI.

### Shared relational schema (Turso): `schema/turso.sql`

`tables`, `columns`, `jobs`, `lineage_chain`, `quality_rules`, `flags`.
Indexes: `lineage_chain(mart_column_id, chain_order)`,
`lineage_chain(source_column_id)`, `columns(table_id)`, `quality_rules(job_id)`.

### Canonical output: `schema/provenance.schema.json`

`meta`, `tables[]`, `columns[]`, `jobs[]`, `lineage_chain[]`,
`quality_rules[]`, `flags[]`, `reconciliation{}`. Stable content-hashed IDs.

**Controlled vocabularies (model + DDL + JSON Schema must agree):**

- `Layer`: RAW | ODS | STG | MART
- `StepType`: DATA | PROC_SQL | PROC_FORMAT | PROC_SORT | SCD2 | RSUBMIT | OTHER
- `UnmappableReason` (flag reason / column unmappable):
  macro_unresolved | dynamic_column_name | hand_written_code |
  remote_execution | step_count_mismatch | multi_source
- `Frequency`: daily | weekly | monthly | quarterly | annual

### Design constraints to enforce

- JSON is the single seam. Tools 2/3 never read `.sas` or logs.
- Idempotent, content-hashed IDs. Re-runs diff cleanly.
- Flag, never drop. Every unresolved item is visible and reasoned.
- Human-in-the-loop is first-class. Source documents win, always.
- Best-effort contracts emit even when incomplete, flags carried through.
- Keep the UI boring. SQLite in, markdown + mermaid out.

---

## Delivered

The pipeline emits real column-level lineage end to end. Highlights, condensed
from the original build log:

**Tool 1: Parser****
- `data_step` + `proc_sql` emit real column-level `LineageChain` objects with
  verbatim SQL/assignment `transformation_logic`, `chain_order`, `step_type`,
  and nullable `data_type_at_step`. Column derivations are fully auditable.
- Multi-source DATA steps (MERGE >1 table) capture all sources and emit a
  `multi_source` flag so per-column upstream remains unresolved.
- PROC SQL uses stdlib `sql_tokeniser` (depth-aware, string-literal skipping) to
  harvest FROM/JOIN sources including comma-joins and subqueries (replaced regex).
- LIBNAME inheritance: `builder._resolve_librefs` pushes engine/path/layer from
  the libref onto datasets and their columns.
- Freshness consolidated in `parser/freshness.py` (name tokens + log cadence).
- Macro resolution: log SYMBOLGEN/MLOGIC first, then `%LET`/`%SYSLPUT` code
  fallback (`LogResolver.load_code_macros`, log wins). MPRINT captured.
- Datatypes lifted from PROC CONTENTS log rows into `Column.data_type`.
- All comment forms stripped before splitting (`/* */`, `%* ;`, `* ;`,
  unterminated blocks).
- Extractors: LIBNAME (incl. DB2 database + SLIBREF server), DATA, PROC SQL,
  generic PROC (table-level + flag), RSUBMIT (inner parse + remote tag + SIGNON
  server), SCD2 (tables + flag), unknown-macro flagging (`MacroCallExtractor`).
- DI autogen column macros resolve or flag `dynamic_column_name`.
- Code-vs-log step-count drift emits a `step_count_mismatch` flag.
- Reconciler `--excel` wired into the CLI over the chain's column map.
- Shared `extractors/_factory.py` (`new_table`, `new_column`, `flag_macro`).

**Tool 2: Schema Mapper****
- Loads provenance into Turso (content-hashed flag IDs, diffable re-runs).
- `--params` → quality_rules, `--owners` → job owner/domain (`enrich.py`).
- ODCS contract per table, flags carried through; `mapping_gaps.json`.

**Tool 3: Web UI**
- Views: column provenance (+ mermaid), reverse lineage, flag dashboard.

`patterns.py` is fully exercised: zero unused patterns.

---

## Outstanding

Real scope still open, ranked. Column-level lineage is complete and shipped; the items below are in-flight UI enhancements and data enrichment.

### 1. Flows: `flow_id` / `flow_count` (blocked on source)

`builder.py` hardcodes `Job.flow_id=None` → `flow_count` always 0. Flow
membership lives in the scheduler's metadata, not in `.sas`/logs. **Needs a
decision:** which manifest/export is the flow source, then a loader keyed by job
name (same pattern as `enrich.load_owners`).

### 2. Tool 3: remaining views

Built: provenance, reverse lineage, flag dashboard. Missing per spec:

- **Filter view**: by layer / domain / flow / frequency.
- **Quality view**: per contract, rules and the columns they govern.
- **Gaps view**: missing owner/domain, unmatched quality rules (data already
  in `mapping_gaps.json` / `quality_rules` / `jobs`).
- **Export**: any lineage chain as markdown.

All are flat SQLite queries + a template; no new dependencies.

### 3. Open items (blocked on real-estate samples)

- Exact DI autogen macro naming convention: confirm against a real job. The
  `DI_AUTOGEN_COL` pattern is a best-effort guess until then.
- Log format anchors that reliably mark macro resolution and step boundaries.
- Bank-holiday / calendar exception source for freshness (config vs audit log).
- ODCS version target and the modelgen tool's exact input expectations.

### 4. Heuristic hardening (after first real run)

SCD2 and generic-PROC steps emit tables + a flag but no column-level lineage.
Column detail is opaque from code alone. Revisit with real logs, watching the
flag tallies in `parse_report.json`.

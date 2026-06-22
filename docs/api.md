# Contents

* [cli](#sas_lineage.parser.cli)
  * [main](#sas_lineage.parser.cli.main)
* [log\_resolver](#sas_lineage.parser.log_resolver)
  * [LogResolver](#sas_lineage.parser.log_resolver.LogResolver)
    * [load\_code\_macros](#sas_lineage.parser.log_resolver.LogResolver.load_code_macros)
    * [run\_timestamps](#sas_lineage.parser.log_resolver.LogResolver.run_timestamps)
    * [log\_step\_count](#sas_lineage.parser.log_resolver.LogResolver.log_step_count)
    * [mprint\_statements](#sas_lineage.parser.log_resolver.LogResolver.mprint_statements)
    * [datatype](#sas_lineage.parser.log_resolver.LogResolver.datatype)
    * [resolve](#sas_lineage.parser.log_resolver.LogResolver.resolve)
* [builder](#sas_lineage.parser.builder)
  * [ProvenanceBuilder](#sas_lineage.parser.builder.ProvenanceBuilder)
* [sql\_tokeniser](#sas_lineage.parser.sql_tokeniser)
  * [Token](#sas_lineage.parser.sql_tokeniser.Token)
    * [kind](#sas_lineage.parser.sql_tokeniser.Token.kind)
    * [value](#sas_lineage.parser.sql_tokeniser.Token.value)
  * [scan\_tokens](#sas_lineage.parser.sql_tokeniser.scan_tokens)
  * [extract\_sql\_tables](#sas_lineage.parser.sql_tokeniser.extract_sql_tables)
* [data\_step](#sas_lineage.parser.extractors.data_step)
  * [DataStepExtractor](#sas_lineage.parser.extractors.data_step.DataStepExtractor)
* [macro\_call](#sas_lineage.parser.extractors.macro_call)
  * [MacroCallExtractor](#sas_lineage.parser.extractors.macro_call.MacroCallExtractor)
* [rsubmit](#sas_lineage.parser.extractors.rsubmit)
  * [RsubmitExtractor](#sas_lineage.parser.extractors.rsubmit.RsubmitExtractor)
* [scd2](#sas_lineage.parser.extractors.scd2)
  * [Scd2Extractor](#sas_lineage.parser.extractors.scd2.Scd2Extractor)
* [proc\_generic](#sas_lineage.parser.extractors.proc_generic)
  * [GenericProcExtractor](#sas_lineage.parser.extractors.proc_generic.GenericProcExtractor)
* [proc\_sql](#sas_lineage.parser.extractors.proc_sql)
  * [ProcSqlExtractor](#sas_lineage.parser.extractors.proc_sql.ProcSqlExtractor)
* [libname](#sas_lineage.parser.extractors.libname)
  * [LibnameExtractor](#sas_lineage.parser.extractors.libname.LibnameExtractor)
* [\_factory](#sas_lineage.parser.extractors._factory)
  * [flag\_macro](#sas_lineage.parser.extractors._factory.flag_macro)
* [extractor](#sas_lineage.parser.extractor)
  * [StepExtractor](#sas_lineage.parser.extractor.StepExtractor)
    * [can\_extract](#sas_lineage.parser.extractor.StepExtractor.can_extract)
    * [extract](#sas_lineage.parser.extractor.StepExtractor.extract)
* [freshness](#sas_lineage.parser.freshness)
  * [infer\_from\_name](#sas_lineage.parser.freshness.infer_from_name)
  * [infer\_from\_log\_timestamps](#sas_lineage.parser.freshness.infer_from_log_timestamps)
* [reconciler](#sas_lineage.parser.reconciler)
  * [reconcile](#sas_lineage.parser.reconciler.reconcile)
* [walker](#sas_lineage.parser.walker)
  * [JobPair](#sas_lineage.parser.walker.JobPair)
    * [log\_path](#sas_lineage.parser.walker.JobPair.log_path)
  * [walk\_pairs](#sas_lineage.parser.walker.walk_pairs)
* [app](#sas_lineage.web_ui.app)
  * [create\_app](#sas_lineage.web_ui.app.create_app)
* [models](#sas_lineage.models)
  * [Layer](#sas_lineage.models.Layer)
  * [StepType](#sas_lineage.models.StepType)
  * [UnmappableReason](#sas_lineage.models.UnmappableReason)
  * [Frequency](#sas_lineage.models.Frequency)
  * [Table](#sas_lineage.models.Table)
  * [Column](#sas_lineage.models.Column)
  * [Job](#sas_lineage.models.Job)
  * [LineageChain](#sas_lineage.models.LineageChain)
  * [QualityRule](#sas_lineage.models.QualityRule)
  * [Flag](#sas_lineage.models.Flag)
  * [ReconciliationResult](#sas_lineage.models.ReconciliationResult)
  * [ProvenanceMeta](#sas_lineage.models.ProvenanceMeta)
  * [Provenance](#sas_lineage.models.Provenance)
* [loader](#sas_lineage.schema_mapper.loader)
  * [ProvenanceLoader](#sas_lineage.schema_mapper.loader.ProvenanceLoader)
    * [connect](#sas_lineage.schema_mapper.loader.ProvenanceLoader.connect)
    * [close](#sas_lineage.schema_mapper.loader.ProvenanceLoader.close)
    * [load](#sas_lineage.schema_mapper.loader.ProvenanceLoader.load)
* [cli](#sas_lineage.schema_mapper.cli)
  * [main](#sas_lineage.schema_mapper.cli.main)
* [odcs](#sas_lineage.schema_mapper.odcs)
  * [generate\_contract](#sas_lineage.schema_mapper.odcs.generate_contract)
* [enrich](#sas_lineage.schema_mapper.enrich)
  * [load\_owners](#sas_lineage.schema_mapper.enrich.load_owners)
  * [load\_quality\_rules](#sas_lineage.schema_mapper.enrich.load_quality_rules)

<a id="sas_lineage.parser.cli"></a>

# cli

CLI entry point for the SAS Parser (Tool 1).

<a id="sas_lineage.parser.cli.main"></a>

#### main

```python
@click.command()
@click.option(
    "--code-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Root directory containing all deployed .sas files.",
)
@click.option(
    "--log-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Root directory containing verbose .log files from SAS execution.",
)
@click.option(
    "--estate",
    default="sas-estate",
    show_default=True,
    help="Estate name to embed in provenance.json metadata.",
)
@click.option(
    "--output",
    default="provenance.json",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Output path for provenance.json.",
)
@click.option(
    "--report",
    default="parse_report.json",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Output path for parse_report.json.",
)
@click.option(
    "--excel",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Optional manual mapping .xlsx (source, target, job) to reconcile.",
)
def main(code_dir: Path, log_dir: Path, estate: str, output: Path,
         report: Path, excel: Path | None) -> None
```

Extract lineage from SAS code and logs, emit provenance.json.

<a id="sas_lineage.parser.log_resolver"></a>

# log\_resolver

Resolve macro variables from verbose execution logs.

Strategy: logs emitted with MPRINT/SYMBOLGEN/MLOGIC options contain
fully-resolved macro variable values. We prefer log-resolved values
over code literals where they conflict, per the plan. Where no log is
available, %LET / %SYSLPUT statements in the code itself are read as a
best-effort fallback (log always wins on conflict).

<a id="sas_lineage.parser.log_resolver.LogResolver"></a>

## LogResolver

```python
class LogResolver()
```

Extracts macro variable resolutions from a SAS log file.

<a id="sas_lineage.parser.log_resolver.LogResolver.load_code_macros"></a>

#### load\_code\_macros

```python
def load_code_macros(code: str) -> None
```

Seed %LET / %SYSLPUT literals from code as a fallback.

Only fills names the log did not already resolve. Log wins.

<a id="sas_lineage.parser.log_resolver.LogResolver.run_timestamps"></a>

#### run\_timestamps

```python
def run_timestamps() -> list[datetime]
```

Return run timestamps found in the log (for cadence inference).

<a id="sas_lineage.parser.log_resolver.LogResolver.log_step_count"></a>

#### log\_step\_count

```python
def log_step_count() -> int
```

Number of DATA/PROC step-completion NOTEs seen in the log.

<a id="sas_lineage.parser.log_resolver.LogResolver.mprint_statements"></a>

#### mprint\_statements

```python
def mprint_statements() -> list[str]
```

Return fully-resolved statement text captured from MPRINT lines.

<a id="sas_lineage.parser.log_resolver.LogResolver.datatype"></a>

#### datatype

```python
def datatype(column_name: str) -> str | None
```

Return the logged SAS datatype (CHAR/NUM) for a column, if known.

<a id="sas_lineage.parser.log_resolver.LogResolver.resolve"></a>

#### resolve

```python
def resolve(value: str) -> tuple[str, bool]
```

Replace &macvar references in value using log-resolved table.

Returns (resolved_value, fully_resolved).
fully_resolved is False if any &macvar remains after substitution.

<a id="sas_lineage.parser.builder"></a>

# builder

ProvenanceBuilder: orchestrates Walker + extractors → Provenance.

Usage:
    builder = ProvenanceBuilder(code_dir, log_dir, estate="acme-risk")
    provenance = builder.build()
    provenance.to_json()

<a id="sas_lineage.parser.builder.ProvenanceBuilder"></a>

## ProvenanceBuilder

```python
class ProvenanceBuilder()
```

Orchestrate extractors over a SAS code dir into a Provenance.

<a id="sas_lineage.parser.sql_tokeniser"></a>

# sql\_tokeniser

Stdlib PROC SQL tokeniser.

A flat regex cannot see paren depth, string literals, or comma-joins, so the
FROM/JOIN table list, subquery boundaries and select-list commas were all
mis-split (F2/F3/F5). This does a single left-to-right scan that skips string
literals and tracks paren depth, then walks the tokens with a depth-keyed
context stack to harvest table references. Comma-joins and tables nested
inside subqueries are included (each FROM at any depth opens its own context,
so nested FROMs are harvested without explicit recursion).

Ported idiomatically from DATALineage/R/proc_sql.R.

<a id="sas_lineage.parser.sql_tokeniser.Token"></a>

## Token

```python
class Token(NamedTuple)
```

<a id="sas_lineage.parser.sql_tokeniser.Token.kind"></a>

#### kind

ident | open | close | comma | semi

<a id="sas_lineage.parser.sql_tokeniser.Token.value"></a>

#### value

lowercased for idents/macros; literal for punctuation

<a id="sas_lineage.parser.sql_tokeniser.scan_tokens"></a>

#### scan\_tokens

```python
def scan_tokens(buffer: str) -> list[Token]
```

Single L→R scan: skip strings, track paren depth, emit tokens.

<a id="sas_lineage.parser.sql_tokeniser.extract_sql_tables"></a>

#### extract\_sql\_tables

```python
def extract_sql_tables(buffer: str) -> list[TableRef]
```

Harvest every FROM/JOIN table ref: comma-joins and nested included.

<a id="sas_lineage.parser.extractors.data_step"></a>

# data\_step

DATA step extractor.

Identifies output dataset, source datasets (SET/MERGE/MODIFY/UPDATE),
and captures assignment/CASE expressions as transformation logic.

Hard cases flagged (not dropped):
  - Unresolved macros in dataset names -> macro_unresolved
  - Dynamic column names (&var-based output) -> dynamic_column_name
  - Hand-written logic with no clear attribution -> hand_written_code

<a id="sas_lineage.parser.extractors.data_step.DataStepExtractor"></a>

## DataStepExtractor

```python
class DataStepExtractor()
```

Extracts column-level lineage from a DATA step block.

<a id="sas_lineage.parser.extractors.macro_call"></a>

# macro\_call

Unknown-macro-call extractor.

A user macro call (%load_risk(...)) can hide an entire transform the parser
cannot see into. SCD2 calls are handled by the SCD2 extractor; SAS
macro-language statements (%let, %if, %do, ...) and common utility functions
are control flow, not lineage. Everything else is flagged for human review
rather than silently dropped.

<a id="sas_lineage.parser.extractors.macro_call.MacroCallExtractor"></a>

## MacroCallExtractor

```python
class MacroCallExtractor()
```

Flags macro invocations that are neither SCD2 nor SAS built-ins.

<a id="sas_lineage.parser.extractors.rsubmit"></a>

# rsubmit

RSUBMIT extractor.

Tags remote execution blocks. Per the plan we *parse the contents* (so remote
lineage is not lost) but mark the execution context: every table discovered
inside the block is flagged is_remote, and a remote_execution flag is raised.

<a id="sas_lineage.parser.extractors.rsubmit.RsubmitExtractor"></a>

## RsubmitExtractor

```python
class RsubmitExtractor()
```

Detects RSUBMIT blocks, parses inner steps, tags them remote.

<a id="sas_lineage.parser.extractors.scd2"></a>

# scd2

SCD Type 2 extractor.

DI Studio generates SCD2 loader macro calls (%di_scd2_load(...)). The internal
column mapping is opaque from code alone, so we capture it as a known transform
type: emit the source/target tables found in the macro arguments, and raise a
flag so a human confirms the column-level detail.

<a id="sas_lineage.parser.extractors.scd2.Scd2Extractor"></a>

## Scd2Extractor

```python
class Scd2Extractor()
```

Detects DI Studio SCD Type 2 macro blocks.

<a id="sas_lineage.parser.extractors.proc_generic"></a>

# proc\_generic

Generic PROC extractor: everything that is not PROC SQL.

PROC SORT/FORMAT/TRANSPOSE/SUMMARY etc. are not column-traced, but they must
not be silently dropped (flag-never-drop). Captures the input (data=) and
output (out=) datasets at table level; flags the column gap for any PROC other
than SORT (a pure reorder that preserves columns unchanged).

<a id="sas_lineage.parser.extractors.proc_generic.GenericProcExtractor"></a>

## GenericProcExtractor

```python
class GenericProcExtractor()
```

Captures non-SQL PROC steps at table level; flags untraced columns.

<a id="sas_lineage.parser.extractors.proc_sql"></a>

# proc\_sql

PROC SQL extractor.

Handles CREATE TABLE ... AS SELECT patterns. Emits the output table, source
tables, the output columns (one per SELECT-list item), the source columns they
derive from, and a column-level lineage edge per derivation carrying the
verbatim expression as transformation_logic.

Unresolvable items (macros in the target or an expression) are flagged, never
dropped. `SELECT *` is left to schema enrichment downstream. No columns are
invented.

<a id="sas_lineage.parser.extractors.proc_sql.ProcSqlExtractor"></a>

## ProcSqlExtractor

```python
class ProcSqlExtractor()
```

Extracts column-level lineage from PROC SQL CREATE TABLE statements.

<a id="sas_lineage.parser.extractors.libname"></a>

# libname

LIBNAME extractor: discovers library references and infers layer/path.

<a id="sas_lineage.parser.extractors.libname.LibnameExtractor"></a>

## LibnameExtractor

```python
class LibnameExtractor()
```

Extracts LIBNAME statements from a code block.

<a id="sas_lineage.parser.extractors._factory"></a>

# \_factory

Shared Table/Column factories for extractors.

Emitted tables/columns are placeholders: engine/path/layer carry defaults
that the builder fills in from the owning LIBNAME (see
`ProvenanceBuilder._resolve_librefs`). Centralised so every extractor agrees
on those defaults rather than copying the same literals.

<a id="sas_lineage.parser.extractors._factory.flag_macro"></a>

#### flag\_macro

```python
def flag_macro(text: str, resolver: LogResolver, ref_id: str,
               flags: list[Flag]) -> None
```

Flag an unresolved macro, distinguishing DI autogen column names.

Resolves first (log, then code %LET fallback); a name resolved there
raises no flag. DI autogen column macros (&input_N_col_name) get the
DYNAMIC_COLUMN_NAME reason; anything else MACRO_UNRESOLVED.

<a id="sas_lineage.parser.extractor"></a>

# extractor

StepExtractor Protocol: the interface all extractors must satisfy.

Each extractor handles one step type (DATA, PROC SQL, RSUBMIT, etc.)
and converts a raw code block + optional log block into typed model objects.

<a id="sas_lineage.parser.extractor.StepExtractor"></a>

## StepExtractor

```python
class StepExtractor(Protocol)
```

Interface for all step-type extractors.

<a id="sas_lineage.parser.extractor.StepExtractor.can_extract"></a>

#### can\_extract

```python
def can_extract(code_block: str) -> bool
```

Return True if this extractor handles the given code block.

<a id="sas_lineage.parser.extractor.StepExtractor.extract"></a>

#### extract

```python
def extract(
    code_block: str, resolver: LogResolver, job_id: str, step_name: str
) -> tuple[list[Table], list[Column], list[LineageChain], list[Flag]]
```

Parse code_block and return discovered entities.

Tables and Columns emitted here are incomplete candidates;
the builder deduplicates and links them into the Provenance.

<a id="sas_lineage.parser.freshness"></a>

# freshness

Freshness / SLA inference (single source of truth).

Strategy: job name tokens first, then log cadence from run timestamps. The
parser owns this because only the parser sees the logs; the inferred frequency
travels in provenance.json and Tool 2 merely carries it into the contract.
Calendar exceptions (bank holidays) noted as best-effort only.

<a id="sas_lineage.parser.freshness.infer_from_name"></a>

#### infer\_from\_name

```python
def infer_from_name(job_name: str) -> tuple[str | None, list[str]]
```

Return (frequency_label, evidence) from job name tokens.

<a id="sas_lineage.parser.freshness.infer_from_log_timestamps"></a>

#### infer\_from\_log\_timestamps

```python
def infer_from_log_timestamps(
        timestamps: list[datetime]) -> tuple[str | None, list[str]]
```

Infer run cadence from a list of log execution timestamps.

Requires at least 3 timestamps for a confident inference.
Returns (frequency_label, evidence).

<a id="sas_lineage.parser.reconciler"></a>

# reconciler

Reconciler: compares parser output against a manual Excel mapping.

Excel never overwrites parser output. Mismatches are flagged for human review.

<a id="sas_lineage.parser.reconciler.reconcile"></a>

#### reconcile

```python
def reconcile(provenance_columns: dict[str, str],
              excel_path: Optional[Path]) -> ReconciliationResult
```

Compare parser-discovered column mappings against an Excel override.

provenance_columns: {source_col_id -> mart_col_id}
excel_path: optional path to .xlsx with columns [source, target, job]

Returns ReconciliationResult with match/mismatch counts.

<a id="sas_lineage.parser.walker"></a>

# walker

Walk the deployed code directory and pair each job with its log.

<a id="sas_lineage.parser.walker.JobPair"></a>

## JobPair

```python
@dataclass
class JobPair()
```

<a id="sas_lineage.parser.walker.JobPair.log_path"></a>

#### log\_path

None when log is missing

<a id="sas_lineage.parser.walker.walk_pairs"></a>

#### walk\_pairs

```python
def walk_pairs(code_dir: Path, log_dir: Path) -> Iterator[JobPair]
```

Yield one JobPair per .sas file found under code_dir.

<a id="sas_lineage.web_ui.app"></a>

# app

Flask web UI for lineage exploration: sparse by design.

Six views backed by flat SQL queries. No heavy JS framework.
Markdown and mermaid diagrams rendered server-side.

<a id="sas_lineage.web_ui.app.create_app"></a>

#### create\_app

```python
def create_app(db_path: Path | None = None) -> Flask
```

Create the Flask app. DB_PATH env var or arg sets the database.

<a id="sas_lineage.models"></a>

# models

Canonical data model: mirrors provenance.json and the Turso schema.

<a id="sas_lineage.models.Layer"></a>

## Layer

```python
class Layer(str, Enum)
```

Data layer classification for SAS tables.

<a id="sas_lineage.models.StepType"></a>

## StepType

```python
class StepType(str, Enum)
```

SAS step type that produced a lineage hop.

<a id="sas_lineage.models.UnmappableReason"></a>

## UnmappableReason

```python
class UnmappableReason(str, Enum)
```

Reason a column or step could not be fully resolved.

<a id="sas_lineage.models.Frequency"></a>

## Frequency

```python
class Frequency(str, Enum)
```

Inferred run cadence for a SAS job.

<a id="sas_lineage.models.Table"></a>

## Table

```python
@dataclass
class Table()
```

A SAS dataset (libref.name) discovered during parsing.

<a id="sas_lineage.models.Column"></a>

## Column

```python
@dataclass
class Column()
```

A column within a discovered SAS table.

<a id="sas_lineage.models.Job"></a>

## Job

```python
@dataclass
class Job()
```

A SAS program (file stem) processed by the parser.

<a id="sas_lineage.models.LineageChain"></a>

## LineageChain

```python
@dataclass
class LineageChain()
```

One hop in the column-level lineage chain from source to MART.

<a id="sas_lineage.models.QualityRule"></a>

## QualityRule

```python
@dataclass
class QualityRule()
```

A data quality check extracted from a SAS job.

<a id="sas_lineage.models.Flag"></a>

## Flag

```python
@dataclass
class Flag()
```

An item that could not be fully parsed and needs human review.

<a id="sas_lineage.models.ReconciliationResult"></a>

## ReconciliationResult

```python
@dataclass
class ReconciliationResult()
```

Summary of parser output vs Excel mapping reconciliation.

<a id="sas_lineage.models.ProvenanceMeta"></a>

## ProvenanceMeta

```python
@dataclass
class ProvenanceMeta()
```

Metadata header written into every provenance.json output.

<a id="sas_lineage.models.Provenance"></a>

## Provenance

```python
@dataclass
class Provenance()
```

Root container for all lineage data emitted by the parser.

<a id="sas_lineage.schema_mapper.loader"></a>

# loader

Load provenance.json into a SQLite/Turso database.

Idempotent: uses INSERT OR REPLACE so re-runs are safe.

<a id="sas_lineage.schema_mapper.loader.ProvenanceLoader"></a>

## ProvenanceLoader

```python
class ProvenanceLoader()
```

Load provenance.json entities into a SQLite/Turso database.

<a id="sas_lineage.schema_mapper.loader.ProvenanceLoader.connect"></a>

#### connect

```python
def connect() -> None
```

Open the database and apply the DDL schema (idempotent).

<a id="sas_lineage.schema_mapper.loader.ProvenanceLoader.close"></a>

#### close

```python
def close() -> None
```

Close the database connection.

<a id="sas_lineage.schema_mapper.loader.ProvenanceLoader.load"></a>

#### load

```python
def load(provenance: Path | dict) -> None
```

Insert all entities using INSERT OR REPLACE.

Accepts a path to provenance.json or an already-parsed (and possibly
enriched) dict.

<a id="sas_lineage.schema_mapper.cli"></a>

# cli

CLI entry point for the Schema Mapper (Tool 2).

<a id="sas_lineage.schema_mapper.cli.main"></a>

#### main

```python
@click.command()
@click.option(
    "--provenance",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to provenance.json (output from sas-parse).",
)
@click.option(
    "--db",
    default="lineage.db",
    show_default=True,
    type=click.Path(path_type=Path),
    help="SQLite database output path for lineage queries.",
)
@click.option(
    "--contracts-dir",
    default="contracts",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Directory for generated ODCS YAML contracts.",
)
@click.option(
    "--gaps",
    default="mapping_gaps.json",
    show_default=True,
    type=click.Path(path_type=Path),
    help="Path for the gaps report.",
)
@click.option(
    "--owners",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Optional owner/domain CSV (job,owner,domain).",
)
@click.option(
    "--params",
    default=None,
    type=click.Path(exists=True, path_type=Path),
    help="Optional quality CSV (job,rule_name,rule_definition,column_id).",
)
def main(provenance: Path, db: Path, contracts_dir: Path, gaps: Path,
         owners: Path | None, params: Path | None) -> None
```

Load provenance into a database and generate ODCS data contracts.

<a id="sas_lineage.schema_mapper.odcs"></a>

# odcs

ODCS contract generator: one contract per data product (table at layer).

Emits best-effort contracts even for flagged/incomplete columns. Flags are
carried into the contract so the UI and humans can see them.

<a id="sas_lineage.schema_mapper.odcs.generate_contract"></a>

#### generate\_contract

```python
def generate_contract(table: dict, columns: list[dict], job: dict | None,
                      quality_rules: list[dict], flags: list[dict],
                      output_dir: Path) -> Path
```

Generate one ODCS YAML contract for a table.

<a id="sas_lineage.schema_mapper.enrich"></a>

# enrich

Manual Tool 2 inputs: owner/domain and the quality-rule parameters table.

Both are CSV, keyed by job name (the clean, readable form the plan calls for).
Neither overwrites parser output. They add the human-supplied facts the parser
cannot know.

  owners.csv   : job,owner,domain
  params.csv   : job,rule_name,rule_definition,column_id   (column_id optional)

<a id="sas_lineage.schema_mapper.enrich.load_owners"></a>

#### load\_owners

```python
def load_owners(path: Path) -> dict[str, dict[str, str | None]]
```

Return {job_name: {"owner": ..., "domain": ...}} from a CSV.

<a id="sas_lineage.schema_mapper.enrich.load_quality_rules"></a>

#### load\_quality\_rules

```python
def load_quality_rules(path: Path, jobs: list[dict]) -> list[dict]
```

Build quality_rule dicts from a CSV, keyed to jobs by name.


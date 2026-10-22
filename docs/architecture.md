# 👻 Architecture

wraith-sas-lineage is a pipeline: SAS code in, ODCS contracts and a queryable lineage graph out. Three tools. One JSON seam.

---

## Pipeline overview

```mermaid
flowchart TD
    SAS["SAS DI Studio\n(LSF on Unix)"] --> CODE[".sas files"]
    SAS --> LOGS["Verbose logs\n(SYMBOLGEN / MLOGIC)"]

    CODE --> PARSE["sas-parse\nWalker + LogResolver\n+ Extractors"]
    LOGS --> PARSE

    PARSE --> PROV["provenance.json\n(the seam)"]

    PROV --> MAP["sas-map\nProvenanceLoader\n+ ODCS generator\n+ Gaps report"]

    MAP --> DB["lineage.db\n(SQLite / Turso)"]
    MAP --> ODCS["ODCS contracts\nconsumed by wraith-modelgen"]
    MAP --> GAPS["mapping_gaps.json"]

    DB --> UI["sas-ui\nFlask lineage explorer"]

    UI --> FLAGS["/flags\nall extraction flags"]
    UI --> PROV_VIEW["/provenance?col_id\nupstream chain"]
    UI --> LIN["/lineage?col_id\ndownstream to MARTs"]
```

---

## Data layers

SAS estate layers map to canonical values throughout the schema:

```mermaid
flowchart LR
    RAW["RAW\n(landing)"] --> ODS["ODS\n(cleansed)"]
    ODS --> STG["STG\n(conformed)"]
    STG --> MART["MART\n(consumption)"]
```

Lineage chains track column flow from RAW through to MART. The `lineage_chain` table stores one row per source→mart column pair with chain order.

---

## Tool 1: Parser

```mermaid
flowchart TD
    WALKER["Walker\nrglob *.sas\npair with *.log"] --> PAIR["JobPair\nname, code_path, log_path"]
    PAIR --> RESOLVER["LogResolver\nSYMBOLGEN / MLOGIC\ndict of resolved values"]
    PAIR --> SPLITTER["_split_into_blocks\nDATA → RUN\nPROC → RUN/QUIT\nRSUBMIT → ENDRSUBMIT\n%MACRO → %MEND\neverything else → globals_N"]
    SPLITTER --> EXTRACTORS["Extractors\nLibname / DataStep / ProcSQL\nGenericProc / Rsubmit / Scd2"]
    RESOLVER --> EXTRACTORS
    EXTRACTORS --> BUILDER["ProvenanceBuilder\nmerge by stable ID, dedup\nstitch column edges into chains\ninherit engine/layer by libref"]
    BUILDER --> PROV["Provenance\n→ provenance.json"]
```

### Step splitter

`_split_into_blocks(code)` scans a SAS source file and splits it into `(step_name, block)` pairs at block boundaries:

| Step type | Terminates at |
|---|---|
| `DATA` | `RUN;` |
| `PROC` | `RUN;` or `QUIT;` |
| `RSUBMIT` | `ENDRSUBMIT;` (inner `RUN;` is not a terminator) |
| `%MACRO` | `%MEND;` |
| Global (LIBNAME, %LET, OPTIONS) | collected into `globals_N` blocks |

Block comments (`/* ... */`) are stripped before scanning.

### Macro resolution

Log-first strategy:

```mermaid
flowchart LR
    REF["&macro_var\nin code"] --> LOG{"In LogResolver\ndictionary?"}
    LOG -->|"yes"| RESOLVED["Resolved value\nfully_resolved=True"]
    LOG -->|"no"| PARTIAL{"Any part\nresolvable?"}
    PARTIAL -->|"yes"| PART["Partial resolution\nfully_resolved=False"]
    PARTIAL -->|"no"| FLAG["Flag: macro_unresolved\nsnippet captured"]
```

### Stable IDs

All IDs are content-hashed: `<prefix>_<sha256[:12]>`. Inputs are uppercased before hashing. IDs are case-insensitive and stable across re-runs.

| Entity | Prefix | Hash input |
|---|---|---|
| Table | `tbl_` | `LIBREF.NAME` |
| Column | `col_` | `TABLE_ID.NAME` |
| Job | `job_` | `JOB_NAME` |
| Lineage chain | `lc_` | `MART_COL_ID.SOURCE_COL_ID.ORDER` |
| Quality rule | `qr_` | `JOB_ID.RULE_NAME` |

### Column-level lineage

Each DATA step and PROC SQL statement emits:

- **Columns:** one `Column` object per output column (derived from assignment, SELECT list, etc.)
- **LineageChain:** one chain hop per transformation, carrying:
  - `transformation_logic`: the verbatim SQL expression, CASE/WHEN, or assignment text (auditable at source)
  - `step_type`: the SAS step that performed the transformation
  - `chain_order`: position in the full source→MART chain (0 = direct source)
  - `data_type_at_step`: nullable, inferred from PROC CONTENTS logs
  - `unmappable_reason`: populated if the chain hop could not be fully resolved

The builder stitches per-step edges into full source→MART chains, so a single flat query on `lineage_chain` ordered by `chain_order` answers the complete provenance of any MART column. Unresolvable items are flagged rather than dropped, so lineage graphs are queryable even when incomplete.

---

## Tool 2: Schema Mapper

```mermaid
flowchart TD
    PROV["provenance.json"] --> ENRICH["enrich\nowners CSV → jobs\nparams CSV → quality_rules"]
    ENRICH --> LOADER["ProvenanceLoader\nINSERT OR REPLACE\nidempotent"]
    LOADER --> DB["lineage.db\n(turso.sql DDL)"]

    ENRICH --> ODCS_GEN["odcs.generate_contract\nper table (freshness carried\nfrom provenance.json)"]
    ODCS_GEN --> YAML["LAYER_TABLE.yml\nODCS v2.3.0"]

    ENRICH --> GAPS["gaps.generate_gaps_report"]
    GAPS --> GAPS_JSON["mapping_gaps.json"]
```

---

## Tool 3: Web UI

Local Flask app. SQLite connection per request via `g.db`. No write endpoints.

```mermaid
flowchart LR
    DB["lineage.db"] --> APP["Flask create_app(db_path)"]
    APP --> FLAGS["/flags\nGROUP BY reason"]
    APP --> PROV["/provenance?col_id\nlineage_chain JOIN columns JOIN tables\nMermaid flowchart"]
    APP --> LIN["/lineage?col_id\nreverse lineage\ndownstream to MART"]
```

---

## Module map

| Module | Responsibility |
|---|---|
| `models.py` | All dataclasses and enums. Single source of truth for the domain. |
| `ids.py` | Content-hashed stable ID generators. |
| `parser/patterns.py` | SAS regex library. |
| `parser/walker.py` | Filesystem traversal; pairs `.sas` with `.log`. |
| `parser/log_resolver.py` | Parses SYMBOLGEN/MLOGIC lines; resolves `&macro_var`; collects run timestamps. |
| `parser/freshness.py` | Infers run frequency from job-name tokens or log run timestamps. |
| `parser/builder.py` | Orchestrates walker, splitter, extractors; stitches column edges into chains; inherits engine/layer by libref. |
| `parser/extractor.py` | `StepExtractor` Protocol: the extractor interface. |
| `parser/extractors/` | One extractor per SAS step type. |
| `parser/reconciler.py` | Excel mapping reconciliation (openpyxl). |
| `schema_mapper/loader.py` | Loads provenance into SQLite. Applies `schema/turso.sql` DDL. |
| `schema_mapper/odcs.py` | Generates ODCS v2.3.0 YAML per table. |
| `schema_mapper/enrich.py` | Merges manual owner/domain and quality-rule CSVs (keyed by job name). |
| `schema_mapper/gaps.py` | Generates `mapping_gaps.json`. |
| `web_ui/app.py` | Flask factory. |
| `web_ui/views/` | Three route handlers: flags, provenance, lineage. |

---

## Design decisions

**Flag-never-drop.** Unresolvable items become `Flag` objects. They propagate into ODCS under `lineageFlags` and are queryable from the UI. Silent discard would mean incorrect lineage graphs.

**Log-first macro resolution.** SAS DI Studio generates `&input_N_col_name` / `&output_N_col_name` macro variables for column aliases. These cannot be resolved from code alone. SYMBOLGEN logs are the authoritative source.

**All extractors run per block.** There is no `break` after first match. A RSUBMIT block containing a LIBNAME statement triggers both `LibnameExtractor` and `RsubmitExtractor`. Extractors are designed to be additive.

**Single JSON seam.** `provenance.json` is the only interface between Tool 1 and Tools 2/3. Each tool is independently invocable, testable, and replaceable.

**Stdlib tokeniser for PROC SQL.** A flat regex cannot see paren depth, string literals, or distinguish FROM commas from select-list commas. The `sql_tokeniser.py` module performs a single left-to-right scan that tracks parenthesis depth and skips quoted strings (including SAS doubled-quote escapes `''` and `""`), then walks the token stream to harvest all FROM/JOIN tables including those in subqueries and comma-joins. This replaced an earlier regex that mis-split multi-table sources.

[![Documentation](https://img.shields.io/badge/docs-live-brightgreen)](https://www.thomaspeoples.com/gitea-repos/wraith-sas-lineage/)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

# 👻 wraith-sas-lineage
### *SAS Lineage Extraction for the Ghost Stack*

**wraith-sas-lineage** extracts data lineage from SAS DI Studio code and verbose execution logs, maps it to Open Data Contract Standard (ODCS) contracts, and serves a local lineage explorer. One JSON artefact connects all three tools.

Designed for large SAS estates running on Unix. Output feeds [wraith-modelgen](https://git.thomaspeoples.com/thomaspeoples/wraith-modelgen) to auto-generate dbt on BigQuery.

---

## Three tools. One seam.

```
.sas + .log files
      │
      ▼
  sas-parse  ──►  provenance.json
                       │
                       ▼
                   sas-map  ──►  lineage.db  +  ODCS contracts  +  gaps report
                                     │
                                     ▼
                                  sas-ui  ──►  localhost:5000
```

| Command | Input | Output |
|---|---|---|
| `sas-parse` | `.sas` files + verbose logs | `provenance.json` |
| `sas-map` | `provenance.json` | `lineage.db`, ODCS YAML contracts, `mapping_gaps.json`, `lineage_diff.json` |
| `sas-ui` | `lineage.db` | Local lineage explorer |

---

## Install

```bash
uv tool install wraith-sas-lineage
```

Or for development:

```bash
git clone https://git.thomaspeoples.com/thomaspeoples/wraith-sas-lineage.git
cd wraith-sas-lineage
uv run poe setup
```

---

## Quick start

```bash
# Parse SAS code + logs
sas-parse \
  --code-dir /path/to/sas/code \
  --log-dir  /path/to/verbose/logs \
  --estate   acme-sales \
  --output   provenance.json

# Map to DB + ODCS contracts
sas-map \
  --provenance provenance.json \
  --db         lineage.db \
  --contracts-dir contracts/ \
  --gaps       mapping_gaps.json

# Browse lineage
sas-ui --db lineage.db
# → http://localhost:5000/flags      all extraction flags
# → http://localhost:5000/provenance upstream chain for a column
# → http://localhost:5000/lineage    downstream to all MARTs
```

---

## Design principles

**Flag-never-drop.** Unresolved macros, remote execution blocks, and hand-written code surface as `Flag` objects with reason, context, and snippet. Nothing is silently discarded.

**Log-first macro resolution.** `SYMBOLGEN`/`MLOGIC` log lines resolve `&macro_var` references before falling back to the code literal. Accurate lineage for DI Studio estates requires verbose logs.

**Single seam.** `provenance.json` is the only interface between tools. Each tool is independently runnable and testable.

**Content-hashed stable IDs.** Table, column, job, and lineage chain IDs are `SHA-256[:12]` of their canonical string. Same estate, same run, same IDs.

---

## Layer vocabulary

| SAS layer | Schema value |
|---|---|
| RAW | `RAW` |
| ODS | `ODS` |
| STG | `STG` |
| MART | `MART` |

---

## Developer quality gate

```bash
uv run poe test       # pytest (interactive)
uv run poe test-ci    # pytest + coverage ≥ 80%
uv run poe lint       # ruff check
uv run poe format     # ruff format
uv run poe docs-serve # mkdocs at localhost:8000
```

All commits go through commitizen:

```bash
uv run cz commit
```

---

*Part of the [Ghost Stack](https://git.thomaspeoples.com/thomaspeoples). Sovereign. Self-hosted. No nonsense.*

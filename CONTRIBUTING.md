# Contributing to wraith-sas-lineage

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
git clone https://git.thomaspeoples.com/thomaspeoples/wraith-sas-lineage.git
cd wraith-sas-lineage
uv run poe setup
```

This syncs all dependencies and installs pre-commit hooks.

## Running tests

```bash
uv run poe test
```

Coverage must stay above 80%. The suite runs without any external services — no SAS licence, no database connections, no network.

## Code style

Ruff handles formatting and linting:

```bash
uv run poe lint
uv run poe format
```

Line length is 79 characters.

## Commits

Commits follow the Ghost Stack convention via commitizen:

```
👻 <type>/<ticket>: <message>
```

```bash
uv run cz commit
```

Do not bypass pre-commit hooks with `--no-verify`.

## Pull requests

- One concern per PR.
- Include or update tests for any behaviour change.
- If the change affects the JSON provenance schema or the Turso DDL, update `schema/` and the relevant `docs/` page.
- Run the full pre-commit suite before opening: `uv run pre-commit run --all-files`.

## Adding a new extractor

1. Create `src/sas_lineage/parser/extractors/<name>.py` implementing the `StepExtractor` protocol.
2. Register it in `parser/cli.py` via `builder.register(MyExtractor())`.
3. Add tests in `tests/test_parser/test_extractors.py`.
4. Add fixture SAS snippets to `tests/test_parser/fixtures/` if needed.

Extractors must be additive — they receive a block and return what they find. Never raise; return a `Flag` instead.

## Reporting issues

Open a Gitea issue with the SAS snippet (anonymised), the log excerpt, and the exact command you ran. For extraction failures, include the `parse_report.json` and relevant entries from `mapping_gaps.json`.

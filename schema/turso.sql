-- SAS Lineage — Turso (SQLite) DDL
-- Load target for Tool 2; query surface for Tool 3.
-- Re-runnable: all tables use CREATE TABLE IF NOT EXISTS.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tables (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    libref          TEXT NOT NULL,
    engine          TEXT NOT NULL,
    path            TEXT NOT NULL,
    layer           TEXT NOT NULL CHECK (layer IN ('RAW', 'ODS', 'STG', 'MART')),
    is_remote       INTEGER NOT NULL DEFAULT 0 CHECK (is_remote IN (0, 1)),
    meta_id         TEXT,
    is_intermediate INTEGER NOT NULL DEFAULT 0 CHECK (is_intermediate IN (0, 1))
);

CREATE TABLE IF NOT EXISTS columns (
    id          TEXT PRIMARY KEY,
    table_id    TEXT NOT NULL REFERENCES tables(id),
    name        TEXT NOT NULL,
    layer       TEXT NOT NULL CHECK (layer IN ('RAW', 'ODS', 'STG', 'MART')),
    data_type   TEXT NOT NULL,
    nullable    INTEGER NOT NULL DEFAULT 1 CHECK (nullable IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_columns_table ON columns(table_id);

CREATE TABLE IF NOT EXISTS jobs (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    flow_id             TEXT,
    frequency           TEXT CHECK (frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual') OR frequency IS NULL),
    frequency_evidence  TEXT,   -- JSON array serialised as text
    owner               TEXT,
    domain              TEXT
);

CREATE TABLE IF NOT EXISTS lineage_chain (
    id                      TEXT PRIMARY KEY,
    mart_column_id          TEXT NOT NULL REFERENCES columns(id),
    source_column_id        TEXT NOT NULL REFERENCES columns(id),
    chain_order             INTEGER NOT NULL,
    job_id                  TEXT NOT NULL REFERENCES jobs(id),
    step_name               TEXT NOT NULL,
    step_type               TEXT NOT NULL CHECK (step_type IN (
                                'DATA', 'PROC_SQL', 'PROC_FORMAT',
                                'PROC_SORT', 'SCD2', 'RSUBMIT', 'OTHER'
                            )),
    transformation_logic    TEXT NOT NULL DEFAULT '',
    data_type_at_step       TEXT,
    nullable_at_step        INTEGER CHECK (nullable_at_step IN (0, 1) OR nullable_at_step IS NULL),
    unmappable_reason       TEXT CHECK (unmappable_reason IN (
                                'macro_unresolved', 'dynamic_column_name',
                                'hand_written_code', 'remote_execution',
                                'step_count_mismatch', 'multi_source'
                            ) OR unmappable_reason IS NULL),
    evidence                TEXT CHECK (evidence IN (
                                'metadata_macro', 'parsed_sql', 'log_confirmed'
                            ) OR evidence IS NULL)
);

CREATE TABLE IF NOT EXISTS table_lineage (
    id                  TEXT PRIMARY KEY,
    source_table_id     TEXT NOT NULL REFERENCES tables(id),
    target_table_id     TEXT NOT NULL REFERENCES tables(id),
    job_id              TEXT NOT NULL REFERENCES jobs(id),
    step_name           TEXT NOT NULL,
    transform_type      TEXT NOT NULL DEFAULT '',
    evidence            TEXT CHECK (evidence IN (
                            'metadata_macro', 'parsed_sql', 'log_confirmed'
                        ) OR evidence IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_tl_source ON table_lineage(source_table_id);
CREATE INDEX IF NOT EXISTS idx_tl_target ON table_lineage(target_table_id);

CREATE INDEX IF NOT EXISTS idx_lc_mart    ON lineage_chain(mart_column_id, chain_order);
CREATE INDEX IF NOT EXISTS idx_lc_source  ON lineage_chain(source_column_id);
CREATE INDEX IF NOT EXISTS idx_lc_job     ON lineage_chain(job_id);

CREATE TABLE IF NOT EXISTS quality_rules (
    id                      TEXT PRIMARY KEY,
    job_id                  TEXT NOT NULL REFERENCES jobs(id),
    rule_name               TEXT NOT NULL,
    rule_definition         TEXT NOT NULL,
    applies_to_column_id    TEXT REFERENCES columns(id)
);

CREATE INDEX IF NOT EXISTS idx_qr_job     ON quality_rules(job_id);
CREATE INDEX IF NOT EXISTS idx_qr_column  ON quality_rules(applies_to_column_id);

CREATE TABLE IF NOT EXISTS flags (
    id          TEXT PRIMARY KEY,
    ref_id      TEXT NOT NULL,
    reason      TEXT NOT NULL CHECK (reason IN (
                    'macro_unresolved', 'dynamic_column_name',
                    'hand_written_code', 'remote_execution',
                    'step_count_mismatch', 'multi_source'
                )),
    context     TEXT NOT NULL DEFAULT '',
    snippet     TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_flags_ref  ON flags(ref_id);

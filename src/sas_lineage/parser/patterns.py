"""
SAS PERL regex patterns translated to Python re.

Sources:
  SPICE_v0_6.sas: Thomas Peoples (2018)
  SAS/CONNECT documentation for RSUBMIT/SIGNON patterns
"""

import re

# ---------------------------------------------------------------------------
# LIBNAME
# ---------------------------------------------------------------------------

# /libname\s+(\w+)|soix/   (case-insensitive, dotall)
LIBNAME_STMT = re.compile(r"libname\s+(\w+)", re.IGNORECASE)

# Extract quoted path from LIBNAME
LIBNAME_PATH = re.compile(
    r"""libname\s+\w+[^;]+['"]([^'"]+)['"]""", re.IGNORECASE
)

# DB2 datasource keyword: database=X or dsn=X or datasrc=X
LIBNAME_DB2 = re.compile(
    r"(?:database|dsn|datasrc)\s*=\s*(\w+)", re.IGNORECASE
)

# SLIBREF= for remote library alias
LIBNAME_SLIBREF = re.compile(
    r"libname\s+(\w+)\s+slibref\s*=\s*(\w+)\s+server\s*=\s*(&?\w+)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# DATA step
# ---------------------------------------------------------------------------

DATA_STMT = re.compile(r"\A\s*data\s+", re.IGNORECASE)

# Capture output dataset (with optional libref)
DATA_TARGET = re.compile(
    r"\A\s*data\s+([A-Za-z]\w{0,7})\.(\w+)|" r"\A\s*data\s+(&?\w+)",
    re.IGNORECASE,
)

# SET / MERGE / MODIFY / UPDATE: keyword (group1) + clause body (group2) up
# to ';'. All source datasets are parsed from the body in _parse_sources, not
# just the first (F9).
SET_STMT = re.compile(r"\b(SET|MERGE|MODIFY|UPDATE)\b([^;]*);", re.IGNORECASE)

# NULL datastep
DATA_NULL = re.compile(r"\A\s*data\s+_null_\s*;", re.IGNORECASE)

# DATA-step assignment statement: lhs = rhs  (group1 lhs, group2 rhs).
# Anchored on statement start (^ or the preceding ;), so mid-expression "="
# (comparisons in IF/WHERE) is not mistaken for an assignment.
DATA_ASSIGN = re.compile(
    r"(?:^|;)\s*([A-Za-z_]\w*)\s*=\s*([^;]+)", re.MULTILINE
)

# Bare identifier not immediately followed by "(" (i.e. not a function call).
BARE_IDENT = re.compile(r"\b([A-Za-z_]\w*)\b(?!\s*\()")

# ---------------------------------------------------------------------------
# PROC
# ---------------------------------------------------------------------------

PROC_STMT = re.compile(r"\bproc\s+(\w+)\b", re.IGNORECASE)
PROC_SQL = re.compile(r"\bproc\s+sql\b", re.IGNORECASE)

# data= / out= dataset args on a PROC statement (group1 libref, group2 dsn)
PROC_DATA_ARG = re.compile(
    r"\bdata\s*=\s*(?:([A-Za-z]\w{0,7})\.)?(\w+)", re.IGNORECASE
)
PROC_OUT_ARG = re.compile(
    r"\bout\s*=\s*(?:([A-Za-z]\w{0,7})\.)?(\w+)", re.IGNORECASE
)

# PROC SQL: CREATE TABLE ... AS
SQL_CREATE_TABLE = re.compile(
    r"\bcreate\s+table\s+" r"(?:([A-Za-z]\w{0,7})\.)?(\w+)" r"\s+as\b",
    re.IGNORECASE,
)

# PROC SQL: CREATE TABLE [lib.]tbl AS SELECT. group1 libref, group2 table.
# The select-list/from-clause split and source-table harvest are done by
# sql_tokeniser (F2/F3/F5); a flat regex cannot see paren depth.
SQL_CREATE_AS_SELECT = re.compile(
    r"create\s+table\s+(?:([A-Za-z]\w{0,7})\.)?(\w+)\s+as\s+select\b",
    re.IGNORECASE,
)

# Trailing "AS alias" on a single SELECT-list item.
SQL_ITEM_ALIAS = re.compile(r"\bas\s+(\w+)\s*$", re.IGNORECASE)

# A qualified column reference alias.col within an expression.
SQL_QUALIFIED_COL = re.compile(r"\b([A-Za-z]\w*)\.(\w+)\b")

# ---------------------------------------------------------------------------
# RSUBMIT / SIGNON / SIGNOFF
# ---------------------------------------------------------------------------

RSUBMIT_START = re.compile(r"\brsubmit\b", re.IGNORECASE)
RSUBMIT_SERVER = re.compile(r"\brsubmit\s+(&?\w+)\b", re.IGNORECASE)
RSUBMIT_END = re.compile(r"\bendrsubmit\b", re.IGNORECASE)

SIGNON_STMT = re.compile(r"\bsignon\b", re.IGNORECASE)
SIGNON_REMOTE = re.compile(
    r"\bsignon\b.*\bremote\s*=\s*(&?\w+)", re.IGNORECASE
)
SIGNOFF_STMT = re.compile(r"\bsignoff\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Macro
# ---------------------------------------------------------------------------

MACRO_DEF = re.compile(r"%macro\s+(\w+)\b", re.IGNORECASE)
MACRO_CALL = re.compile(r"%(\w+)\s*(?:\(|;)", re.IGNORECASE)
MACRO_VAR_REF = re.compile(r"&(\w+)\.?")
MACRO_LET = re.compile(r"%let\s+(\w+)\s*=\s*([^;]+);", re.IGNORECASE)
MACRO_SYSLPUT = re.compile(r"%syslput\s+(\w+)\s*=\s*([^/;]+)", re.IGNORECASE)

# DI Studio autogen macro column pattern: &input_N_col_name style
# Emitted by the DI Studio "User-written transformations" and SCD macros.
DI_AUTOGEN_COL = re.compile(
    r"&(input_\d+_col_name|output_\d+_col_name)\b", re.IGNORECASE
)

# SCD Type 2 DI Studio macro block signature: %scd2, %di_scd2_load, etc.
SCD2_MACRO = re.compile(r"%(?:\w+_)?scd2?\w*\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

C_COMMENT_FULL = re.compile(r"/\*.*?\*/", re.DOTALL)
C_COMMENT_OPEN = re.compile(r"/\*")
C_COMMENT_CLOSE = re.compile(r"\*/")
MACRO_COMMENT = re.compile(r"\A\s*%\*[^;]*;", re.IGNORECASE)
STMT_COMMENT = re.compile(r"\A\s*\*[^;]*;", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Log anchors for macro resolution
# ---------------------------------------------------------------------------

# MPRINT/SYMBOLGEN log lines that reveal resolved macro variable values
LOG_MPRINT = re.compile(r"^MPRINT\((\w+)\):\s+(.+)$", re.IGNORECASE)
LOG_SYMBOLGEN = re.compile(
    r"SYMBOLGEN:\s+Macro variable (\w+) resolves to (.+)$", re.IGNORECASE
)
LOG_MLOGIC_VAR = re.compile(
    r"MLOGIC\((\w+)\):\s+%LET\s+(\w+)\s*=\s*(.+)$", re.IGNORECASE
)

# Step boundary: NOTE: DATA statement used
LOG_DATA_NOTE = re.compile(r"^NOTE:\s+DATA statement used", re.IGNORECASE)
LOG_PROC_NOTE = re.compile(r"^NOTE:\s+PROCEDURE (\w+) used", re.IGNORECASE)

# Runtime row counts: table creation and data set size NOTEs
LOG_TABLE_CREATED = re.compile(
    r"^NOTE:\s+Table\s+(\S+)\s+created,\s+with\s+(\d+)\s+rows",
    re.IGNORECASE,
)
LOG_DATASET_OBS = re.compile(
    r"^NOTE:\s+The data set\s+(\S+)\s+has\s+(\d+)\s+observations",
    re.IGNORECASE,
)

# Datatype from PROC CONTENTS / dictionary.columns log output
LOG_DATATYPE = re.compile(r"(\w+)\s+(\w+)\s+(Char|Num)\s+(\d+)", re.IGNORECASE)

# ISO-8601 run timestamps a scheduler may stamp into the log; used to infer
# cadence when a job's log spans multiple runs.
LOG_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)")

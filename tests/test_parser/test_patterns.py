"""Tests for SAS regex patterns."""

from sas_lineage.parser import patterns

# ---------------------------------------------------------------------------
# LIBNAME
# ---------------------------------------------------------------------------


def test_libname_stmt_matches():
    line = "libname RISKODS BASE '/data/ods/risk';"
    m = patterns.LIBNAME_STMT.search(line)
    assert m and m.group(1).upper() == "RISKODS"


def test_libname_stmt_case_insensitive():
    m = patterns.LIBNAME_STMT.search("LIBNAME WORK '/tmp';")
    assert m and m.group(1).upper() == "WORK"


def test_libname_path_single_quotes():
    m = patterns.LIBNAME_PATH.search("libname X BASE '/data/path';")
    assert m and m.group(1) == "/data/path"


def test_libname_path_double_quotes():
    m = patterns.LIBNAME_PATH.search('libname X BASE "/data/path";')
    assert m and m.group(1) == "/data/path"


def test_libname_slibref():
    line = "libname rwkmart SLIBREF=work SERVER=&server;"
    m = patterns.LIBNAME_SLIBREF.search(line)
    assert m and m.group(1).upper() == "RWKMART"


# ---------------------------------------------------------------------------
# DATA step
# ---------------------------------------------------------------------------


def test_data_stmt_matches():
    assert patterns.DATA_STMT.search("data work.output;")
    assert patterns.DATA_STMT.search("  DATA WORK.OUTPUT;")


def test_data_null_matches():
    assert patterns.DATA_NULL.search("data _null_;")
    assert patterns.DATA_NULL.search("DATA _NULL_ ;")


def test_data_target_with_libref():
    m = patterns.DATA_TARGET.search("data RISKODS.ALL_EMP;")
    assert m and m.group(1).upper() == "RISKODS"
    assert m.group(2).upper() == "ALL_EMP"


def test_data_target_no_libref():
    m = patterns.DATA_TARGET.search("data output_table;")
    assert m and m.group(3).upper() == "OUTPUT_TABLE"


# ---------------------------------------------------------------------------
# SET / MERGE / MODIFY / UPDATE
# ---------------------------------------------------------------------------


def test_set_stmt_with_libref():
    m = patterns.SET_STMT.search("set RISKODS.SOURCE_TABLE;")
    assert m and m.group(1).lower() == "set"
    assert "RISKODS.SOURCE_TABLE" in m.group(2)


def test_set_stmt_no_libref():
    m = patterns.SET_STMT.search("set staging_table;")
    assert m and "staging_table" in m.group(2)


def test_merge_stmt_captures_all_sources():
    m = patterns.SET_STMT.search("merge base_table(in=a) trans_table(in=b);")
    assert m and m.group(1).lower() == "merge"
    assert "base_table" in m.group(2) and "trans_table" in m.group(2)


# ---------------------------------------------------------------------------
# PROC
# ---------------------------------------------------------------------------


def test_proc_sql():
    assert patterns.PROC_SQL.search("proc sql;")
    assert patterns.PROC_SQL.search("PROC SQL noprint;")


def test_proc_stmt_extracts_name():
    m = patterns.PROC_STMT.search("proc sort data=work.x;")
    assert m and m.group(1).upper() == "SORT"


def test_sql_create_table():
    sql = "create table RISKODS.OUTPUT as select * from SOURCE;"
    m = patterns.SQL_CREATE_TABLE.search(sql)
    assert m and m.group(1).upper() == "RISKODS"
    assert m.group(2).upper() == "OUTPUT"


def test_sql_create_table_no_libref():
    m = patterns.SQL_CREATE_TABLE.search("create table my_table as")
    assert m and m.group(2).upper() == "MY_TABLE"


# ---------------------------------------------------------------------------
# RSUBMIT / SIGNON
# ---------------------------------------------------------------------------


def test_rsubmit_start():
    assert patterns.RSUBMIT_START.search("rsubmit server1;")
    assert patterns.RSUBMIT_START.search("RSUBMIT;")


def test_rsubmit_server():
    m = patterns.RSUBMIT_SERVER.search("rsubmit PROD_SERVER;")
    assert m and m.group(1).upper() == "PROD_SERVER"


def test_rsubmit_end():
    assert patterns.RSUBMIT_END.search("endrsubmit;")
    assert patterns.RSUBMIT_END.search("ENDRSUBMIT ;")


def test_signon():
    assert patterns.SIGNON_STMT.search("signon remote=server user=usr;")


# ---------------------------------------------------------------------------
# Macro
# ---------------------------------------------------------------------------


def test_macro_def():
    m = patterns.MACRO_DEF.search("%macro job_start(JobName=);")
    assert m and m.group(1).lower() == "job_start"


def test_macro_var_ref():
    ms = list(patterns.MACRO_VAR_REF.finditer("libname &lib. '/&path.';"))
    names = [m.group(1) for m in ms]
    assert "lib" in names
    assert "path" in names


def test_macro_let():
    m = patterns.MACRO_LET.search("%let dt = 20260620;")
    assert m and m.group(1) == "dt"
    assert m.group(2).strip() == "20260620"


# ---------------------------------------------------------------------------
# Log anchors
# ---------------------------------------------------------------------------


def test_log_symbolgen():
    line = "SYMBOLGEN:  Macro variable DT resolves to 20260620"
    m = patterns.LOG_SYMBOLGEN.search(line)
    assert m and m.group(1) == "DT"
    assert m.group(2).strip() == "20260620"


def test_log_proc_note():
    line = "NOTE: PROCEDURE SQL used (Total process time):"
    m = patterns.LOG_PROC_NOTE.search(line)
    assert m and m.group(1).upper() == "SQL"

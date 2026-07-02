"""Tests for the patterns.py TODOs wired into the parser."""

from __future__ import annotations

from sas_lineage.models import UnmappableReason
from sas_lineage.parser.builder import ProvenanceBuilder, _strip_comments
from sas_lineage.parser.extractors._factory import flag_macro
from sas_lineage.parser.extractors.libname import LibnameExtractor
from sas_lineage.parser.extractors.macro_call import MacroCallExtractor
from sas_lineage.parser.extractors.rsubmit import RsubmitExtractor
from sas_lineage.parser.log_resolver import LogResolver

_NO_LOG = LogResolver(None)


# --- flag_macro / DI autogen --------------------------------------------


def test_flag_macro_di_autogen_is_dynamic():
    flags: list = []
    flag_macro("&input_1_col_name", _NO_LOG, "ref", flags)
    assert flags[0].reason == UnmappableReason.DYNAMIC_COLUMN_NAME


def test_flag_macro_generic_is_unresolved():
    flags: list = []
    flag_macro("&some_unknown", _NO_LOG, "ref", flags)
    assert flags[0].reason == UnmappableReason.MACRO_UNRESOLVED


def test_flag_macro_resolved_raises_nothing():
    resolver = LogResolver(None)
    resolver.load_code_macros("%let DSN = REAL;")
    flags: list = []
    flag_macro("&DSN", resolver, "ref", flags)
    assert flags == []


# --- LogResolver: code macros, datatypes, mprint ------------------------


def test_code_macro_fallback_when_no_log():
    resolver = LogResolver(None)
    resolver.load_code_macros("%let TBL = SALES; %syslput YR = 2026;")
    assert resolver.get("TBL") == "SALES"
    assert resolver.get("YR") == "2026"


def test_log_value_wins_over_code(tmp_path):
    log = tmp_path / "j.log"
    log.write_text("SYMBOLGEN:  Macro variable DSN resolves to FROM_LOG\n")
    resolver = LogResolver(log)
    resolver.load_code_macros("%let DSN = FROM_CODE;")
    assert resolver.get("DSN") == "FROM_LOG"


def test_datatype_from_log(tmp_path):
    log = tmp_path / "j.log"
    log.write_text("1   ORDER_AMT   Num   8\n")
    resolver = LogResolver(log)
    assert resolver.datatype("ORDER_AMT") == "NUM"


def test_mprint_captured(tmp_path):
    log = tmp_path / "j.log"
    log.write_text("MPRINT(LOAD):   create table X as select 1;\n")
    resolver = LogResolver(log)
    assert any("create table" in s for s in resolver.mprint_statements())


# --- LIBNAME DB2 / SLIBREF ----------------------------------------------


def test_libname_db2_captures_database():
    ex = LibnameExtractor()
    code = "libname DB2LIB DB2 schema=SALES database=PR01;"
    tables, *_ = ex.extract(code, _NO_LOG, "j", "s")
    assert tables[0].engine == "DB2"
    assert tables[0].path == "PR01"


def test_libname_slibref_captures_server():
    ex = LibnameExtractor()
    code = "libname RLIB slibref=SALESODS server=PROD;"
    tables, *_ = ex.extract(code, _NO_LOG, "j", "s")
    assert tables[0].is_remote
    assert tables[0].path == "PROD"


# --- RSUBMIT SIGNON fallback --------------------------------------------


def test_rsubmit_server_from_signon():
    ex = RsubmitExtractor()
    code = (
        "rsubmit; signon remote=PROD01;\n"
        "data WORK.OUT; set WORK.IN; run;\n"
        "endrsubmit;"
    )
    _, _, _, flags = ex.extract(code, _NO_LOG, "j", "s")
    assert any(
        f.reason == UnmappableReason.REMOTE_EXECUTION and "PROD01" in f.context
        for f in flags
    )


# --- comment stripping ---------------------------------------------------


def test_strip_all_comment_forms():
    code = (
        "%* macro comment;\n"
        "* statement comment;\n"
        "/* block comment */\n"
        "data x; set y; run;\n"
    )
    clean = _strip_comments(code)
    assert "comment" not in clean
    assert "data x" in clean


def test_strip_unterminated_block_comment():
    code = "data x; run;\n/* dangling never closed\ndata y; run;"
    clean = _strip_comments(code)
    assert "data y" not in clean


# --- datatype applied to columns end to end -----------------------------


def test_builder_applies_log_datatype(tmp_path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "log"
    code_dir.mkdir()
    log_dir.mkdir()
    (code_dir / "j.sas").write_text(
        "data MART.OUT; set SALESODS.SRC; AMOUNT = QTY * PRICE; run;"
    )
    (log_dir / "j.log").write_text("1  AMOUNT  Num  8\n")

    builder = ProvenanceBuilder(code_dir, log_dir, estate="t")
    from sas_lineage.parser.extractors.data_step import DataStepExtractor

    builder.register(DataStepExtractor())
    prov = builder.build()

    amount = next(c for c in prov.columns if c.name == "AMOUNT")
    assert amount.data_type == "NUM"


# --- MACRO_CALL: flag unknown macros ------------------------------------


def test_unknown_macro_flagged():
    ex = MacroCallExtractor()
    _, _, _, flags = ex.extract("%load_sales(in=A, out=B);", _NO_LOG, "j", "s")
    assert flags[0].reason == UnmappableReason.HAND_WRITTEN_CODE
    assert "load_sales" in flags[0].context


def test_sas_builtin_macros_not_flagged():
    ex = MacroCallExtractor()
    code = "%let x=1; %put hello; %do; %end;"
    _, _, _, flags = ex.extract(code, _NO_LOG, "j", "s")
    assert flags == []


def test_scd2_macro_not_flagged_as_unknown():
    ex = MacroCallExtractor()
    _, _, _, flags = ex.extract(
        "%di_scd2_load(in=A, out=B);", _NO_LOG, "j", "s"
    )
    assert flags == []


# --- LOG step-count sanity ----------------------------------------------


def test_step_count_mismatch_flagged(tmp_path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "log"
    code_dir.mkdir()
    log_dir.mkdir()
    # One code step, but the log records two completed steps -> drift.
    (code_dir / "j.sas").write_text("data WORK.OUT; set WORK.IN; run;")
    (log_dir / "j.log").write_text(
        "NOTE: DATA statement used (Total process time):\n"
        "NOTE: PROCEDURE SQL used (Total process time):\n"
    )

    builder = ProvenanceBuilder(code_dir, log_dir, estate="t")
    from sas_lineage.parser.extractors.data_step import DataStepExtractor

    builder.register(DataStepExtractor())
    prov = builder.build()

    assert any(
        f.reason == UnmappableReason.STEP_COUNT_MISMATCH for f in prov.flags
    )

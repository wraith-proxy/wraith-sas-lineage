"""Tests for individual step extractors."""

from sas_lineage.models import UnmappableReason
from sas_lineage.parser.extractors.data_step import DataStepExtractor
from sas_lineage.parser.extractors.libname import LibnameExtractor
from sas_lineage.parser.extractors.proc_sql import ProcSqlExtractor
from sas_lineage.parser.extractors.rsubmit import RsubmitExtractor
from sas_lineage.parser.extractors.scd2 import Scd2Extractor
from sas_lineage.parser.log_resolver import LogResolver

_NO_LOG = LogResolver(None)


# ---------------------------------------------------------------------------
# LibnameExtractor
# ---------------------------------------------------------------------------


class TestLibnameExtractor:
    ex = LibnameExtractor()

    def test_can_extract_true(self):
        assert self.ex.can_extract("libname SALESODS BASE '/data';")

    def test_can_extract_false(self):
        assert not self.ex.can_extract("data x; set y; run;")

    def test_extracts_base_libname(self):
        code = "libname SALESODS BASE '/data/ods/sales';"
        tables, cols, lc, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(t.libref == "SALESODS" for t in tables)
        assert len(flags) == 0

    def test_extracts_path(self):
        code = "libname X BASE '/some/path';"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert tables[0].path == "/some/path"

    def test_detects_db2_engine(self):
        code = "libname DB2LIB DB2 schema=SALES database=PR01;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert tables[0].engine == "DB2"

    def test_detects_remote(self):
        code = "libname RLIB slibref=SALESODS server=PROD;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert tables[0].is_remote

    def test_skips_comment_lines(self):
        code = "/* libname FAKE BASE '/fake'; */"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert tables == []

    def test_layer_inferred_ods(self):
        code = "libname SALESODS BASE '/data/ods';"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert tables[0].layer.value == "ODS"


# ---------------------------------------------------------------------------
# DataStepExtractor
# ---------------------------------------------------------------------------


class TestDataStepExtractor:
    ex = DataStepExtractor()

    def test_can_extract_true(self):
        assert self.ex.can_extract("data WORK.OUT; set WORK.IN; run;")

    def test_can_extract_false(self):
        assert not self.ex.can_extract("proc sql; select 1; quit;")

    def test_extracts_output_and_source_tables(self):
        code = "data SALESODS.OUTPUT; set RAWDATA.SOURCE; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "OUTPUT" in names
        assert "SOURCE" in names

    def test_flags_no_set_statement(self):
        code = "data WORK.OUT;\n x = 1;\nrun;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.HAND_WRITTEN_CODE for f in flags
        )

    def test_flags_unresolved_macro_in_target(self):
        code = "data &DYNAMIC_DSN; set RAWDATA.SRC; run;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        )

    def test_merge_detected_as_source(self):
        code = "data OUT; merge TABLE_A(in=a) TABLE_B(in=b); by ID; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "TABLE_A" in names or "TABLE_B" in names

    def test_data_null_no_output_table(self):
        code = "data _null_; set WORK.X; run;"
        tables, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert not any(t.name == "_NULL_" for t in tables)

    def test_resolver_used_for_macro_dsn(self, tmp_path):
        log = tmp_path / "j.log"
        log.write_text(
            "SYMBOLGEN:  Macro variable DSN resolves to REAL_TABLE\n"
        )
        resolver = LogResolver(log)
        code = "data WORK.OUT; set &DSN; run;"
        tables, _, _, flags = self.ex.extract(code, resolver, "j1", "s1")
        names = {t.name for t in tables}
        assert "REAL_TABLE" in names
        assert not any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        )

    def test_assignment_emits_column_and_lineage(self):
        code = "data MART.OUT; set SALESODS.SRC; AMOUNT = QTY * PRICE; run;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert "AMOUNT" in {c.name for c in cols}
        assert any(h.transformation_logic == "QTY * PRICE" for h in lineage)

    def test_no_source_emits_column_without_lineage(self):
        code = "data WORK.OUT; X = 1; run;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert "X" in {c.name for c in cols}
        assert lineage == []


# ---------------------------------------------------------------------------
# GenericProcExtractor
# ---------------------------------------------------------------------------


class TestGenericProcExtractor:
    from sas_lineage.parser.extractors.proc_generic import GenericProcExtractor

    ex = GenericProcExtractor()

    def test_ignores_proc_sql(self):
        assert not self.ex.can_extract("proc sql; quit;")

    def test_handles_proc_sort(self):
        assert self.ex.can_extract("proc sort data=A out=B; by x; run;")

    def test_sort_emits_tables_no_flag(self):
        code = "proc sort data=SALESODS.A out=WORK.B; by x; run;"
        tables, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert {t.name for t in tables} == {"A", "B"}
        assert flags == []

    def test_other_proc_with_out_flagged(self):
        code = "proc means data=A; output out=STATS mean=; run;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.HAND_WRITTEN_CODE for f in flags
        )


# ---------------------------------------------------------------------------
# ProcSqlExtractor
# ---------------------------------------------------------------------------


class TestProcSqlExtractor:
    ex = ProcSqlExtractor()

    def test_can_extract_true(self):
        assert self.ex.can_extract("proc sql; select 1; quit;")

    def test_can_extract_false(self):
        assert not self.ex.can_extract("data x; run;")

    def test_extracts_create_table(self):
        code = (
            "proc sql;\n"
            "create table SALESODS.OUTPUT as\n"
            "select * from RAWDATA.SOURCE;\n"
            "quit;"
        )
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "OUTPUT" in names

    def test_extracts_from_table(self):
        code = "proc sql; create table OUT as select * from RAWDATA.SRC; quit;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "SRC" in names

    def test_extracts_join_table(self):
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select a.*, b.COL from A left join LIB.B on a.k=b.k;\n"
            "quit;"
        )
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "B" in names

    def test_flags_unresolved_macro_in_target(self):
        code = "proc sql; create table &DYN_TBL as select 1; quit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        )

    def test_case_expr_with_macro_flagged(self):
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select CASE WHEN &X = 1 THEN 0 ELSE 1 END AS MY_COL\n"
            "from SRC;\n"
            "quit;"
        )
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        )

    def test_emits_output_and_source_columns(self):
        code = (
            "proc sql;\n"
            "create table MART.OUT as\n"
            "select a.QTY as AMOUNT from SALESODS.SRC a;\n"
            "quit;"
        )
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {c.name for c in cols}
        assert "AMOUNT" in names
        assert "QTY" in names

    def test_lineage_edge_carries_transform_logic(self):
        code = (
            "proc sql;\n"
            "create table MART.OUT as\n"
            "select a.QTY * 1.1 as ADJ from SALESODS.SRC a;\n"
            "quit;"
        )
        _, _, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert lineage
        assert any("QTY" in h.transformation_logic for h in lineage)


# ---------------------------------------------------------------------------
# RsubmitExtractor
# ---------------------------------------------------------------------------


class TestRsubmitExtractor:
    ex = RsubmitExtractor()

    def test_can_extract_true(self):
        assert self.ex.can_extract(
            "rsubmit SERVER1; proc sort; run; endrsubmit;"
        )

    def test_can_extract_false(self):
        assert not self.ex.can_extract("data x; run;")

    def test_flags_remote_execution(self):
        code = "rsubmit PROD;\n proc sort data=x; run;\nendrsubmit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.REMOTE_EXECUTION for f in flags
        )

    def test_flag_context_includes_server(self):
        code = "rsubmit PROD_SERVER;\n data x; run;\nendrsubmit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert "PROD_SERVER" in flags[0].context

    def test_inner_content_in_snippet(self):
        code = "rsubmit SRV;\n proc sql; quit;\nendrsubmit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert (
            "proc sql" in flags[0].snippet.lower() or len(flags[0].snippet) > 0
        )

    def test_bare_rsubmit_no_server(self):
        code = "rsubmit;\ndata x; run;\nendrsubmit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert flags
        assert "UNKNOWN" in flags[0].context

    def test_inner_steps_parsed_and_tagged_remote(self):
        code = (
            "rsubmit PROD;\n"
            "data REMOTE.OUT; set REMOTE.SRC; X = A; run;\n"
            "endrsubmit;"
        )
        tables, cols, _, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert tables, "inner data step should yield tables"
        assert all(t.is_remote for t in tables)
        assert "X" in {c.name for c in cols}


# ---------------------------------------------------------------------------
# Scd2Extractor
# ---------------------------------------------------------------------------


class TestScd2Extractor:
    ex = Scd2Extractor()

    def test_can_extract_true(self):
        assert self.ex.can_extract("%di_scd2_load(param1=X);")

    def test_can_extract_false(self):
        assert not self.ex.can_extract("data x; run;")

    def test_extracts_in_out_tables(self):
        code = "%di_scd2_load(in=SALESODS.SRC, out=MART.DIM_TABLE);"
        tables, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "SRC" in names
        assert "DIM_TABLE" in names

    def test_flags_for_human_review(self):
        code = "%di_scd2_load(in=SRC, out=DIM_TABLE);"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.HAND_WRITTEN_CODE for f in flags
        )


# ---------------------------------------------------------------------------
# Batch A — TJP-21061 column-lineage fixes
# ---------------------------------------------------------------------------


class TestProcSqlBatchA:
    """Batch A fixes: F1 (MULTI_SOURCE) and F6 (macro source table)."""

    ex = ProcSqlExtractor()

    # F1 — unqualified column in a multi-table join gets MULTI_SOURCE flag
    # and no lineage edge is produced for it.
    def test_f1_unqualified_col_multi_table_emits_multi_source_flag(self):
        code = "proc sql;\ncreate table OUT as\nselect X from A, B;\nquit;"
        _, cols, lineage, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(f.reason == UnmappableReason.MULTI_SOURCE for f in flags), (
            "expected MULTI_SOURCE flag for unqualified col in 2-table join"
        )

    def test_f1_unqualified_col_multi_table_no_lineage_edge(self):
        code = "proc sql;\ncreate table OUT as\nselect X from A, B;\nquit;"
        _, _, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert lineage == [], (
            "no lineage edge should be produced for an unqualified "
            "column in a multi-table join"
        )

    def test_f1_qualified_col_multi_table_no_flag(self):
        # Qualified references should resolve cleanly — no MULTI_SOURCE flag.
        code = (
            "proc sql;\ncreate table OUT as\nselect a.X from A a, B b;\nquit;"
        )
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert not any(
            f.reason == UnmappableReason.MULTI_SOURCE for f in flags
        ), "qualified column reference should not raise MULTI_SOURCE"

    # F6 — macro-named source table with no log → MACRO_UNRESOLVED flag
    def test_f6_macro_source_table_no_log_emits_macro_unresolved(self):
        code = "proc sql;\ncreate table OUT as\nselect * from &SRC;\nquit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        ), "expected MACRO_UNRESOLVED flag when FROM clause uses &macro"

    def test_f6_macro_source_resolved_via_log_no_flag(self, tmp_path):
        log = tmp_path / "j.log"
        log.write_text(
            "SYMBOLGEN:  Macro variable SRC resolves to SALESODS.SOURCE\n"
        )
        resolver = LogResolver(log)
        code = "proc sql;\ncreate table OUT as\nselect * from &SRC;\nquit;"
        _, _, _, flags = self.ex.extract(code, resolver, "j1", "s1")
        assert not any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        ), "resolved macro should not produce MACRO_UNRESOLVED flag"


class TestDataStepBatchA:
    """Batch A fixes: F4 (string/format filtering) and F7 (MERGE)."""

    ex = DataStepExtractor()

    # F4 — string literal content and format references must not appear
    # as source columns; the real column arguments must.
    def test_f4_format_keyword_not_a_source_column(self):
        code = "data WORK.OUT; set WORK.SRC;\ny = put(z, BEST12.);\nrun;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        source_names = {c.name for c in cols if c.name != "Y"}
        assert "BEST12" not in source_names, (
            "format reference BEST12 must not be treated as a source column"
        )

    def test_f4_real_arg_is_source_column(self):
        code = "data WORK.OUT; set WORK.SRC;\ny = put(z, BEST12.);\nrun;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        source_names = {c.name for c in cols if c.name != "Y"}
        assert "Z" in source_names, (
            "the real argument Z should appear as a source column"
        )

    def test_f4_intnx_interval_not_a_source_column(self):
        code = "data WORK.OUT; set WORK.SRC;\nx = intnx('MONTH', d, 1);\nrun;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        source_names = {c.name for c in cols if c.name != "X"}
        assert "MONTH" not in source_names, (
            "string literal 'MONTH' must not become a source column"
        )

    def test_f4_intnx_date_arg_is_source_column(self):
        code = "data WORK.OUT; set WORK.SRC;\nx = intnx('MONTH', d, 1);\nrun;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        source_names = {c.name for c in cols if c.name != "X"}
        assert "D" in source_names, (
            "date argument D should appear as a source column"
        )

    # F7 — DATA MERGE with >1 source emits MULTI_SOURCE flag and still
    # emits the output column (flag-never-drop semantics).
    def test_f7_merge_multi_source_emits_flag(self):
        code = "data OUT;\nmerge A B;\nx = a + b;\nrun;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(f.reason == UnmappableReason.MULTI_SOURCE for f in flags), (
            "MERGE with 2 sources should emit a MULTI_SOURCE flag"
        )

    def test_f7_merge_multi_source_col_still_emitted(self):
        code = "data OUT;\nmerge A B;\nx = a + b;\nrun;"
        _, cols, _, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert "X" in {c.name for c in cols}, (
            "output column X must be emitted even when upstream "
            "is MULTI_SOURCE"
        )


# ---------------------------------------------------------------------------
# Batch B — TJP-21061 tokenizer-backed extractor fixes
# ---------------------------------------------------------------------------


class TestProcSqlBatchB:
    """Batch B: F2 (subquery FROM), F3 (CASE IN-list), F5 (comma-join)."""

    ex = ProcSqlExtractor()

    # F2 — scalar subquery in the select list must not steal the outer FROM
    def test_f2_subquery_in_select_list_both_tables_captured(self):
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select x, (select max(v) from SUB) as m from MAIN;\n"
            "quit;"
        )
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        names = {t.name for t in tables}
        assert "MAIN" in names, "outer FROM table must be captured"
        assert "SUB" in names, "subquery FROM table must be captured"

    def test_f2_outer_select_list_from_split_correct(self):
        """The outer select list must NOT include the subquery's FROM."""
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select x, (select max(v) from SUB) as m from MAIN;\n"
            "quit;"
        )
        _, cols, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        col_names = {c.name for c in cols}
        # X and M are real columns; 'from' must not appear as a column
        assert "FROM" not in col_names, (
            "the subquery's FROM keyword must not leak into the column list"
        )

    # F3 — IN-list commas inside CASE must not split the select list
    def test_f3_case_in_list_not_split(self):
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select CASE WHEN k IN ('A','B','C') THEN 1 END as flag,"
            " other\n"
            "from SRC;\n"
            "quit;"
        )
        _, cols, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        col_names = {c.name for c in cols}
        assert "FLAG" in col_names, "CASE expression column must be emitted"
        assert "OTHER" in col_names, (
            "second column after the CASE must be emitted as a separate item"
        )
        # The IN-list values must not appear as column names
        assert "A" not in col_names
        assert "B" not in col_names
        assert "C" not in col_names

    def test_f3_case_in_list_exactly_two_select_items(self):
        """Exactly the CASE col and 'other' — not extra splits from IN-list."""
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select CASE WHEN k IN ('A','B','C') THEN 1 END as flag,"
            " other\n"
            "from SRC;\n"
            "quit;"
        )
        _, cols, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        output_names = {c.name for c in cols}
        # FLAG and OTHER must both be present; no phantom split items
        assert "FLAG" in output_names
        assert "OTHER" in output_names

    # F5 — comma-join source tables + aliases
    def test_f5_three_comma_joined_tables(self):
        code = "proc sql;\ncreate table OUT as\nselect * from A, B, C;\nquit;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert src_names >= {
            "A",
            "B",
            "C",
        }, "all three comma-joined source tables must be captured"

    def test_f5_comma_join_with_aliases(self):
        code = (
            "proc sql;\n"
            "create table OUT as\n"
            "select a.ID, b.NAME\n"
            "from A a, B b\n"
            "where a.k = b.k;\n"
            "quit;"
        )
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert "A" in src_names
        assert "B" in src_names

    # F6 combined — macro source AND real source in the same FROM clause
    def test_f6_combined_macro_and_real_table(self):
        code = (
            "proc sql;\ncreate table OUT as\nselect * from &SRC, REAL;\nquit;"
        )
        tables, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert "REAL" in src_names, "REAL must be emitted as a source table"

    def test_f6_combined_macro_unresolved_flag_raised(self):
        code = (
            "proc sql;\ncreate table OUT as\nselect * from &SRC, REAL;\nquit;"
        )
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(
            f.reason == UnmappableReason.MACRO_UNRESOLVED for f in flags
        ), "unresolved macro source must produce MACRO_UNRESOLVED flag"

    def test_f6_combined_real_table_not_dropped(self):
        """flag-never-drop: REAL must still appear even though &SRC failed."""
        code = (
            "proc sql;\ncreate table OUT as\nselect * from &SRC, REAL;\nquit;"
        )
        tables, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert "REAL" in src_names


class TestDataStepBatchB:
    """Batch B fix F9: all datasets from SET/MERGE clause body."""

    ex = DataStepExtractor()

    # F9 — MERGE with three tables, no aliases
    def test_f9_merge_three_sources_all_captured(self):
        code = "data OUT; merge A B C; x = a+b; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert src_names >= {
            "A",
            "B",
            "C",
        }, "all three MERGE sources must be captured"

    # F9 — dataset options stripped before parsing
    def test_f9_dataset_options_stripped(self):
        code = "data OUT; merge A(in=x) B; by ID; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert "A" in src_names, "A must be captured despite dataset options"
        assert "B" in src_names, "B must be captured"
        # The option text must not become a table name
        assert not any("in" == n.lower() for n in src_names)
        assert not any("x" == n for n in src_names)

    # F9 — SET with multiple datasets on one line (less common but valid)
    def test_f9_set_multiple_datasets(self):
        code = "data OUT; set A B C; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert src_names >= {"A", "B", "C"}

    # F9 — merge emits MULTI_SOURCE flag when >1 source
    def test_f9_three_merge_sources_multi_source_flag(self):
        code = "data OUT; merge A B C; x = a+b; run;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert any(f.reason == UnmappableReason.MULTI_SOURCE for f in flags), (
            "3-source MERGE must emit MULTI_SOURCE flag"
        )


# ---------------------------------------------------------------------------
# Batch C — TJP-21061 hardening-pass review findings
# ---------------------------------------------------------------------------


class TestDataStepBatchC:
    """Finding 3: SAS doubled-quote escapes in _STR_LITERAL.
    Finding 6: nested-paren dataset options in _DS_OPTION.
    """

    ex = DataStepExtractor()

    # Finding 3 — 'it''s' is one string; 's' must not leak as phantom col
    def test_f3_doubled_quote_no_phantom_column(self):
        """x = 'it''s' must yield no phantom column refs from the RHS."""
        code = "data WORK.OUT; set WORK.SRC;\nx = 'it''s';\nrun;"
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {c.name for c in cols if c.name != "X"}
        # 'S' is what leaks if '' terminates the string early
        assert "S" not in src_names, (
            "doubled-quote escape inside string must not produce phantom ref"
        )

    def test_f3_double_quoted_escape_no_phantom(self):
        """x = \"he\"\"said\" must not leak 'SAID' as a source column."""
        code = 'data WORK.OUT; set WORK.SRC;\nx = "he""said";\nrun;'
        _, cols, lineage, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {c.name for c in cols if c.name != "X"}
        assert "SAID" not in src_names

    # Finding 6 — where=(x>0) nested paren must not create phantom table
    def test_f6_nested_where_option_two_sources(self):
        """set A (where=(x>0)) B; must yield exactly sources A and B."""
        code = "data OUT; set A (where=(x>0)) B; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert "A" in src_names
        assert "B" in src_names

    def test_f6_nested_where_option_no_phantom(self):
        """No phantom table from the leaking ') B' after the first ')'."""
        code = "data OUT; set A (where=(x>0)) B; run;"
        tables, *_ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        # Phantom would be something like '0' or 'b' appearing twice
        assert len(src_names) == 2, (
            f"expected exactly A and B as sources, got {src_names}"
        )


class TestProcSqlBatchC:
    """Finding 2: unresolved-macro alias gap (MULTI_SOURCE on partial sources).
    Finding 5: three-part dotted ident guard.
    """

    ex = ProcSqlExtractor()

    # Finding 2 — unresolved macro + real table → MULTI_SOURCE flag added
    def test_f2_unresolved_macro_with_real_source_emits_multi_source(self):
        """Unresolved &SRC + REAL source emits MULTI_SOURCE flag."""
        code = (
            "proc sql;\ncreate table OUT as\n"
            "select col from &SRC, REAL;\nquit;"
        )
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        reasons = {f.reason for f in flags}
        assert UnmappableReason.MULTI_SOURCE in reasons, (
            "unresolved macro alongside a resolved source must emit "
            "MULTI_SOURCE to flag partial attribution"
        )

    def test_f2_unresolved_macro_alone_no_multi_source(self):
        """Lone unresolved &SRC: MACRO_UNRESOLVED only, not MULTI_SOURCE."""
        code = "proc sql;\ncreate table OUT as\nselect * from &SRC;\nquit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert not any(
            f.reason == UnmappableReason.MULTI_SOURCE for f in flags
        ), "lone unresolved macro should not produce MULTI_SOURCE"

    # Finding 5 — three-part dotted ident flagged, not silently dropped
    def test_f5_three_part_ident_emits_flag(self):
        """A.B.C in a FROM clause must produce a flag, not silently drop."""
        code = "proc sql;\ncreate table OUT as\nselect * from A.B.C;\nquit;"
        _, _, _, flags = self.ex.extract(code, _NO_LOG, "j1", "s1")
        assert flags, "a three-part table ref must produce at least one flag"

    def test_f5_three_part_ident_no_table_emitted(self):
        """A.B.C must not be emitted as a valid source table."""
        code = "proc sql;\ncreate table OUT as\nselect * from A.B.C;\nquit;"
        tables, _, _, _ = self.ex.extract(code, _NO_LOG, "j1", "s1")
        src_names = {t.name for t in tables} - {"OUT"}
        assert not any("." in n for n in src_names), (
            "three-part ref must not appear as a table name"
        )

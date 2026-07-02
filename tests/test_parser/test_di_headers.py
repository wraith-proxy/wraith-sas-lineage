"""DI boxed-header harvester tests (eval B2)."""

import shutil
from pathlib import Path

from sas_lineage.models import Evidence
from sas_lineage.parser.builder import ProvenanceBuilder
from sas_lineage.parser.di_headers import harvest_di_headers

_DI = Path(__file__).parent / "fixtures" / "di"


def _by_name(tables):
    return {f"{t.libref}.{t.name}": t for t in tables}


class TestHarvest:
    def test_generated_job_tables_with_meta_ids(self):
        code = (_DI / "di_generated_job.sas").read_text()
        tables = harvest_di_headers(code, "job_x").tables
        named = _by_name(tables)
        assert named["RAWLIB.ORDERS"].meta_id == "A5CGXK2Q.BE0001XY"
        assert named["work.W54ABCDE"].meta_id == "A5CGXK2Q.BE0002XZ"
        assert named["MARTLIB.SALES_MART"].meta_id == "A5CGXK2Q.BE0003YA"
        assert len(tables) == 3

    def test_generated_job_table_edges(self):
        code = (_DI / "di_generated_job.sas").read_text()
        harvest = harvest_di_headers(code, "job_x")
        tables, edges = harvest.tables, harvest.table_edges
        named = _by_name(tables)
        assert len(edges) == 2
        first, second = edges
        assert first.source_table_id == named["RAWLIB.ORDERS"].id
        assert first.target_table_id == named["work.W54ABCDE"].id
        assert first.transform_type == "Extract"
        assert second.source_table_id == named["work.W54ABCDE"].id
        assert second.target_table_id == named["MARTLIB.SALES_MART"].id
        assert second.transform_type == "Table Loader"
        assert all(e.evidence == Evidence.METADATA_MACRO for e in edges)
        assert all(e.job_id == "job_x" for e in edges)

    def test_two_sources_fan_in(self):
        code = (_DI / "di_multi_input_ambiguity.sas").read_text()
        harvest = harvest_di_headers(code, "job_x")
        assert len(harvest.tables) == 3
        assert len(harvest.table_edges) == 2
        assert {e.transform_type for e in harvest.table_edges} == {"SQL Join"}

    def test_plain_code_yields_nothing(self):
        code = "data work.a;\n    set work.b;\nrun;\n"
        harvest = harvest_di_headers(code, "job_x")
        assert harvest.tables == [] and harvest.table_edges == []

    def test_ordinary_comment_with_step_word_ignored(self):
        code = "/* Next Step: rewrite this job someday */\ndata a; run;\n"
        harvest = harvest_di_headers(code, "job_x")
        assert harvest.tables == [] and harvest.table_edges == []


class TestMappingMacros:
    def test_single_source_column_edges(self):
        code = (_DI / "di_generated_job.sas").read_text()
        harvest = harvest_di_headers(code, "job_x")
        by_logic = {}
        for e in harvest.column_edges:
            by_logic.setdefault(e.transformation_logic, []).append(e)
        assert set(by_logic) == {
            "ORDER_ID",
            "UPCASE(PROD_SUBCATEGORY)",
            "QTY * PRICE",
        }
        assert len(by_logic["QTY * PRICE"]) == 2
        assert all(
            e.evidence == Evidence.METADATA_MACRO for e in harvest.column_edges
        )
        assert harvest.flags == []

    def test_mapped_columns_carry_types(self):
        code = (_DI / "di_generated_job.sas").read_text()
        harvest = harvest_di_headers(code, "job_x")
        by_name = {}
        for c in harvest.columns:
            by_name.setdefault(c.name, c)
        assert by_name["PROD_CATEGORY"].data_type == "CHAR"
        assert by_name["ORDER_AMT"].data_type == "NUM"

    def test_multi_source_resolved_via_generated_sql(self):
        """B5: alias-qualified SQL disambiguates unqualified inputs."""
        code = (_DI / "di_multi_input_ambiguity.sas").read_text()
        harvest = harvest_di_headers(code, "job_x")
        assert harvest.flags == []
        assert len(harvest.column_edges) == 2
        assert all(
            e.evidence == Evidence.PARSED_SQL for e in harvest.column_edges
        )
        named = _by_name(harvest.tables)
        orders_id = named["ODSLIB.ORDERS"].id
        src_tables = {
            c.table_id
            for c in harvest.columns
            if c.id in {e.source_column_id for e in harvest.column_edges}
        }
        assert src_tables == {orders_id}

    def test_multi_source_without_sql_keeps_flag(self):
        code = (
            "/*==========================================================*\n"
            " * Step:         Join without SQL                           *\n"
            " * Transform:    User Written                               *\n"
            " * Source Table: ODSLIB.ORDERS - a  (A5CGXK2Q.BE0004YB)     *\n"
            " * Source Table: ODSLIB.CUSTOMERS - b (A5CGXK2Q.BE0005YC)   *\n"
            " * Target Table: work.W00XYZAB - out (A5CGXK2Q.BE0006YD)    *\n"
            " *==========================================================*/\n"
            "%let _OUTPUT1 = work.W00XYZAB;\n"
            "%let _OUTPUT1_col0_name = STATUS;\n"
            "%let _OUTPUT1_col0_input = STATUS;\n"
            "%let _OUTPUT1_col0_input_count = 1;\n"
            "%let _OUTPUT1_col0_exp = STATUS;\n"
        )
        harvest = harvest_di_headers(code, "job_x")
        assert harvest.column_edges == []
        (flag,) = harvest.flags
        assert flag.reason.value == "multi_source"
        assert flag.ref_id.endswith(".STATUS")


class TestSyslast:
    def test_header_edges_not_duplicated_by_syslast(self):
        code = (_DI / "di_generated_job.sas").read_text()
        harvest = harvest_di_headers(code, "job_x")
        assert len(harvest.table_edges) == 2

    def test_syslast_chains_headerless_job(self):
        code = (
            "%let SYSLAST = work.stage1;\n"
            "data MARTLIB.FINAL;\n    set work.stage1;\nrun;\n"
            "%let SYSLAST = MARTLIB.FINAL;\n"
        )
        harvest = harvest_di_headers(code, "job_x")
        assert len(harvest.table_edges) == 1
        edge = harvest.table_edges[0]
        named = _by_name(harvest.tables)
        assert edge.source_table_id == named["work.stage1"].id
        assert edge.target_table_id == named["MARTLIB.FINAL"].id
        assert edge.step_name == "SYSLAST"
        assert edge.evidence == Evidence.METADATA_MACRO

    def test_repeated_syslast_value_no_self_edge(self):
        code = "%let SYSLAST = work.stage1;\n%let SYSLAST = work.stage1;\n"
        harvest = harvest_di_headers(code, "job_x")
        assert harvest.table_edges == []


class TestBuilderIntegration:
    def test_build_emits_table_lineage_and_meta_ids(self, tmp_path: Path):
        code_dir = tmp_path / "code"
        log_dir = tmp_path / "logs"
        code_dir.mkdir()
        log_dir.mkdir()
        shutil.copy(_DI / "di_generated_job.sas", code_dir / "DI_JOB.sas")

        builder = ProvenanceBuilder(code_dir, log_dir, estate="test")
        prov = builder.build()

        assert len(prov.table_lineage) == 2
        meta_ids = {t.meta_id for t in prov.tables if t.meta_id}
        assert "A5CGXK2Q.BE0001XY" in meta_ids
        (job,) = prov.jobs
        assert all(e.job_id == job.id for e in prov.table_lineage)

    def test_table_lineage_survives_json_round_trip(self, tmp_path: Path):
        import json

        code_dir = tmp_path / "code"
        log_dir = tmp_path / "logs"
        code_dir.mkdir()
        log_dir.mkdir()
        shutil.copy(_DI / "di_generated_job.sas", code_dir / "DI_JOB.sas")
        prov = ProvenanceBuilder(code_dir, log_dir, estate="t").build()
        data = json.loads(prov.to_json())
        assert len(data["table_lineage"]) == 2
        assert data["table_lineage"][0]["evidence"] == "metadata_macro"

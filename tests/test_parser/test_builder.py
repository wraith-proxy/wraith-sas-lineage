"""Tests for ProvenanceBuilder end-to-end (thin slice)."""

from pathlib import Path

from sas_lineage.parser.builder import ProvenanceBuilder
from sas_lineage.parser.extractors.data_step import DataStepExtractor
from sas_lineage.parser.extractors.libname import LibnameExtractor
from sas_lineage.parser.extractors.proc_sql import ProcSqlExtractor
from sas_lineage.parser.extractors.rsubmit import RsubmitExtractor
from sas_lineage.parser.extractors.scd2 import Scd2Extractor


def _make_estate(tmp_path: Path) -> tuple[Path, Path]:
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    code_dir.mkdir()
    log_dir.mkdir()
    return code_dir, log_dir


def _builder(code_dir: Path, log_dir: Path) -> ProvenanceBuilder:
    b = ProvenanceBuilder(code_dir, log_dir, estate="test-estate")
    b.register(LibnameExtractor())
    b.register(DataStepExtractor())
    b.register(ProcSqlExtractor())
    b.register(RsubmitExtractor())
    b.register(Scd2Extractor())
    return b


def test_build_empty_estate(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    p = _builder(code_dir, log_dir).build()
    assert p.meta.estate == "test-estate"
    assert p.meta.job_count == 0


def test_build_single_job(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "DAILY_LOAD.sas").write_text(
        "libname ODS BASE '/data/ods';\ndata ODS.OUT; set ODS.SRC; run;\n"
    )
    p = _builder(code_dir, log_dir).build()
    assert p.meta.job_count == 1


def test_build_job_name_captured(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "MONTHLY_REPORT.sas").write_text("data x; set y; run;")
    p = _builder(code_dir, log_dir).build()
    assert any(j.name == "MONTHLY_REPORT" for j in p.jobs)


def test_build_frequency_inferred_from_name(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "LOAD_DAILY.sas").write_text("data x; set y; run;")
    p = _builder(code_dir, log_dir).build()
    job = next(j for j in p.jobs if j.name == "LOAD_DAILY")
    assert job.frequency is not None
    assert job.frequency.value == "daily"


def test_build_provenance_to_json(tmp_path: Path):
    import json

    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "JOB_A.sas").write_text(
        "proc sql; create table OUT as select * from SRC; quit;"
    )
    p = _builder(code_dir, log_dir).build()
    raw = p.to_json()
    parsed = json.loads(raw)
    assert parsed["meta"]["estate"] == "test-estate"


def test_build_tables_discovered(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "JOB.sas").write_text(
        "libname RAWDATA BASE '/data/raw';\n"
        "data WORK.OUT; set RAWDATA.SRC; run;\n"
    )
    p = _builder(code_dir, log_dir).build()
    names = {t.name for t in p.tables}
    assert "RAWDATA" in names or "OUT" in names or "SRC" in names


def test_build_rsubmit_flagged(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "REMOTE_JOB.sas").write_text(
        "rsubmit SERVER1;\n proc sort data=x; run;\nendrsubmit;"
    )
    p = _builder(code_dir, log_dir).build()
    assert any(f.reason.value == "remote_execution" for f in p.flags)


def test_build_register_extractor(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    b = ProvenanceBuilder(code_dir, log_dir, estate="t")
    assert len(b._extractors) == 0
    b.register(LibnameExtractor())
    assert len(b._extractors) == 1


def test_build_stitches_multi_step_chain(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "MART_LOAD.sas").write_text(
        "data SALESODS.STG; set SALESODS.SRC; AMOUNT = QTY * PRICE; run;\n"
        "proc sql; create table MART.SALES_FACT as "
        "select s.AMOUNT as FINAL_AMT from SALESODS.STG s; quit;\n"
    )
    p = _builder(code_dir, log_dir).build()
    final = next(c for c in p.columns if c.name == "FINAL_AMT")
    hops = [h for h in p.lineage_chain if h.mart_column_id == final.id]
    assert hops
    # Chain reaches back through the DATA step to QTY/PRICE (order >= 2).
    assert max(h.chain_order for h in hops) >= 2


def test_extractor_edges_carry_parsed_sql_evidence(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "MART_LOAD.sas").write_text(
        "data SALESODS.STG; set SALESODS.SRC; AMOUNT = QTY * PRICE; run;\n"
        "proc sql; create table MART.SALES_FACT as "
        "select s.AMOUNT as FINAL_AMT from SALESODS.STG s; quit;\n"
    )
    p = _builder(code_dir, log_dir).build()
    assert p.lineage_chain
    assert all(h.evidence is not None for h in p.lineage_chain)
    assert {h.evidence.value for h in p.lineage_chain} == {"parsed_sql"}


def test_mprint_confirms_executed_edges(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "J.sas").write_text(
        "data SALESODS.STG; set SALESODS.SRC; AMOUNT = QTY * PRICE; run;\n"
    )
    (log_dir / "J.log").write_text(
        "MPRINT(LOADER):   data SALESODS.STG;\n"
        "MPRINT(LOADER):   set SALESODS.SRC;\n"
        "MPRINT(LOADER):   AMOUNT = QTY * PRICE;\n"
        "MPRINT(LOADER):   run;\n"
    )
    p = _builder(code_dir, log_dir).build()
    assert p.lineage_chain
    assert {h.evidence.value for h in p.lineage_chain} == {"log_confirmed"}


def test_mprint_reveals_log_only_edges(tmp_path: Path):
    """Code hides the transform in a macro call; only the log shows it."""
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "J.sas").write_text("%load_sales(in=SRC, out=STG);\n")
    (log_dir / "J.log").write_text(
        "MPRINT(LOAD_SALES):   data SALESODS.STG;\n"
        "MPRINT(LOAD_SALES):   set SALESODS.SRC;\n"
        "MPRINT(LOAD_SALES):   AMOUNT = QTY * PRICE;\n"
        "MPRINT(LOAD_SALES):   run;\n"
    )
    p = _builder(code_dir, log_dir).build()
    log_edges = [
        h for h in p.lineage_chain if h.evidence.value == "log_confirmed"
    ]
    assert log_edges, "log-only hops must be captured"


def test_code_only_edges_keep_static_evidence(tmp_path: Path):
    """Log lacks the DATA step: edge stays parsed_sql for the diff."""
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "J.sas").write_text(
        "data SALESODS.STG; set SALESODS.SRC; AMOUNT = QTY * PRICE; run;\n"
    )
    (log_dir / "J.log").write_text("MPRINT(OTHER):   options nosymbolgen;\n")
    p = _builder(code_dir, log_dir).build()
    assert {h.evidence.value for h in p.lineage_chain} == {"parsed_sql"}


def test_build_libname_inheritance(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "J.sas").write_text(
        "libname SALESODS DB2 database=PR01;\n"
        "data SALESODS.OUT; set SALESODS.SRC; X = A; run;\n"
    )
    p = _builder(code_dir, log_dir).build()
    out = next(t for t in p.tables if t.name == "OUT")
    assert out.engine == "DB2"
    assert out.layer.value == "ODS"
    # Library pseudo-rows are dropped from the dataset list.
    assert not any(t.name == t.libref for t in p.tables)


def test_work_w_tables_classified_intermediate(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "J.sas").write_text(
        "data work.W54ABCDE;\n    set RAWLIB.ORDERS;\nrun;\n"
        "data work.KEEP_ME;\n    set work.W54ABCDE;\nrun;\n"
    )
    p = _builder(code_dir, log_dir).build()
    by_name = {t.name: t for t in p.tables}
    assert by_name["W54ABCDE"].is_intermediate is True
    assert by_name["KEEP_ME"].is_intermediate is False
    assert by_name["ORDERS"].is_intermediate is False

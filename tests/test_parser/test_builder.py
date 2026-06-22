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
        "data RISKODS.STG; set RISKODS.SRC; EXPOSURE = BAL * RATE; run;\n"
        "proc sql; create table MART.MART as "
        "select s.EXPOSURE as FINAL_EXP from RISKODS.STG s; quit;\n"
    )
    p = _builder(code_dir, log_dir).build()
    final = next(c for c in p.columns if c.name == "FINAL_EXP")
    hops = [h for h in p.lineage_chain if h.mart_column_id == final.id]
    assert hops
    # Chain reaches back through the DATA step to BAL/RATE (order >= 2).
    assert max(h.chain_order for h in hops) >= 2


def test_build_libname_inheritance(tmp_path: Path):
    code_dir, log_dir = _make_estate(tmp_path)
    (code_dir / "J.sas").write_text(
        "libname RISKODS DB2 database=PR01;\n"
        "data RISKODS.OUT; set RISKODS.SRC; X = A; run;\n"
    )
    p = _builder(code_dir, log_dir).build()
    out = next(t for t in p.tables if t.name == "OUT")
    assert out.engine == "DB2"
    assert out.layer.value == "ODS"
    # Library pseudo-rows are dropped from the dataset list.
    assert not any(t.name == t.libref for t in p.tables)

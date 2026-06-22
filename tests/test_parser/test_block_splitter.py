"""Tests for _split_into_blocks step-boundary detection."""

from pathlib import Path

from sas_lineage.parser.builder import _split_into_blocks


def test_single_proc_sql():
    code = "proc sql;\ncreate table X as select 1;\nquit;\n"
    blocks = _split_into_blocks(code)
    assert any("SQL" in name for name, _ in blocks)


def test_single_data_step():
    code = "data WORK.OUT;\n  set WORK.IN;\nrun;\n"
    blocks = _split_into_blocks(code)
    names = [n for n, _ in blocks]
    assert any("data" in n for n in names)


def test_rsubmit_not_terminated_by_run():
    code = (
        "rsubmit PROD;\n"
        # run; inside rsubmit must NOT end the block
        "  proc sort data=x; run;\n"
        "endrsubmit;\n"
    )
    blocks = _split_into_blocks(code)
    rsubmit_blocks = [(n, b) for n, b in blocks if "rsubmit" in n]
    assert len(rsubmit_blocks) == 1
    _, body = rsubmit_blocks[0]
    assert "endrsubmit" in body.lower()


def test_globals_before_proc():
    code = (
        "libname ODS BASE '/data/ods';\n"
        "%let dt = 20260620;\n"
        "proc sql;\ncreate table X as select 1;\nquit;\n"
    )
    blocks = _split_into_blocks(code)
    names = [n for n, _ in blocks]
    assert any("globals" in n for n in names)
    assert any("SQL" in n for n in names)


def test_multiple_steps():
    code = (
        "proc sql;\ncreate table A as select 1;\nquit;\n"
        "data WORK.B;\nset WORK.A;\nrun;\n"
    )
    blocks = _split_into_blocks(code)
    assert len(blocks) == 2


def test_macro_def_isolated():
    code = (
        "%macro LOAD_DATA(dt=);\n"
        "  data X; set Y; run;\n"
        "%mend LOAD_DATA;\n"
        "proc sql;\ncreate table Z as select 1;\nquit;\n"
    )
    blocks = _split_into_blocks(code)
    names = [n for n, _ in blocks]
    assert any("macro" in n for n in names)


def test_block_content_correct():
    code = (
        "proc sql;\ncreate table OUT as select * from SRC;\nquit;\n"
        "data WORK.D;\nset OUT;\nrun;\n"
    )
    blocks = _split_into_blocks(code)
    sql_text = next(b for n, b in blocks if "SQL" in n)
    assert "create table" in sql_text.lower()
    data_text = next(b for n, b in blocks if "data" in n)
    assert "set out" in data_text.lower()


def test_sample_fixture(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "sample_job.sas"
    code = fixture.read_text()
    blocks = _split_into_blocks(code)
    names = [n for n, _ in blocks]
    assert any("globals" in n for n in names)  # libname + %let
    assert any("SQL" in n for n in names)  # proc sql
    assert any("data" in n for n in names)  # data step
    assert any("rsubmit" in n for n in names)  # rsubmit block


def test_empty_code():
    blocks = _split_into_blocks("")
    assert blocks  # never empty list

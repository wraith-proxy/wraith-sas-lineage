"""Tests for content-hashed stable ID generation."""

from sas_lineage.ids import (
    column_id,
    job_id,
    lineage_chain_id,
    quality_rule_id,
    table_id,
)


def test_table_id_format():
    tid = table_id("RISKODS", "ALL_EMP")
    assert tid.startswith("tbl_")
    assert len(tid) == len("tbl_") + 12


def test_table_id_stable():
    assert table_id("RISKODS", "ALL_EMP") == table_id("RISKODS", "ALL_EMP")


def test_table_id_case_insensitive():
    assert table_id("riskods", "all_emp") == table_id("RISKODS", "ALL_EMP")


def test_column_id_format():
    tid = table_id("RISKODS", "ALL_EMP")
    cid = column_id(tid, "EXPOSURE_AMT")
    assert cid.startswith("col_")
    assert len(cid) == len("col_") + 12


def test_column_id_different_columns():
    tid = table_id("RISKODS", "ALL_EMP")
    assert column_id(tid, "EXPOSURE_AMT") != column_id(tid, "ACCOUNT_NO")


def test_job_id_format():
    jid = job_id("RISK_ODS_LOAD_DAILY")
    assert jid.startswith("job_")
    assert len(jid) == len("job_") + 12


def test_lineage_chain_id_stable():
    mart = column_id(table_id("MART", "MART"), "COL_A")
    src = column_id(table_id("ODS", "SOURCE"), "COL_B")
    lc1 = lineage_chain_id(mart, src, 1)
    lc2 = lineage_chain_id(mart, src, 1)
    assert lc1 == lc2


def test_lineage_chain_id_order_matters():
    mart = column_id(table_id("MART", "MART"), "COL_A")
    src = column_id(table_id("ODS", "SOURCE"), "COL_B")
    assert lineage_chain_id(mart, src, 1) != lineage_chain_id(mart, src, 2)


def test_quality_rule_id_format():
    jid = job_id("RISK_ODS_LOAD")
    qrid = quality_rule_id(jid, "EXPOSURE_NON_NEGATIVE")
    assert qrid.startswith("qr_")

"""Tests for data model serialisation (to_dict / to_json roundtrip)."""

import json

from sas_lineage.models import (
    Column,
    Flag,
    Frequency,
    Job,
    Layer,
    LineageChain,
    Provenance,
    ProvenanceMeta,
    QualityRule,
    ReconciliationResult,
    StepType,
    Table,
    UnmappableReason,
)


def _sample_provenance() -> Provenance:
    meta = ProvenanceMeta(
        generated_at="2026-06-20T00:00:00Z",
        parser_version="0.0.1",
        estate="test",
        job_count=1,
        flow_count=1,
    )
    table = Table(
        id="tbl_aabbccddeeff",
        name="ALL_EMP",
        libref="SALESODS",
        engine="BASE",
        path="/data/ods",
        layer=Layer.ODS,
        is_remote=False,
    )
    col = Column(
        id="col_aabbccddeeff",
        table_id="tbl_aabbccddeeff",
        name="ORDER_AMT",
        layer=Layer.ODS,
        data_type="NUM",
        nullable=True,
    )
    job = Job(
        id="job_aabbccddeeff",
        name="SALES_ODS_LOAD_DAILY",
        flow_id="flow_001",
        frequency=Frequency.DAILY,
        frequency_evidence=["name_token:daily"],
    )
    lc = LineageChain(
        id="lc_aabbccddeeff",
        mart_column_id="col_aabbccddeeff",
        source_column_id="col_112233445566",
        chain_order=1,
        job_id="job_aabbccddeeff",
        step_name="Extract",
        step_type=StepType.PROC_SQL,
        transformation_logic="CASE WHEN bal < 0 THEN 0 ELSE bal END",
        data_type_at_step="NUM",
        nullable_at_step=False,
        unmappable_reason=None,
    )
    qr = QualityRule(
        id="qr_aabbccddeeff",
        job_id="job_aabbccddeeff",
        rule_name="AMOUNT_NON_NEGATIVE",
        rule_definition="ORDER_AMT >= 0",
        applies_to_column_id="col_aabbccddeeff",
    )
    flag = Flag(
        ref_id="lc_aabbccddeeff",
        reason=UnmappableReason.MACRO_UNRESOLVED,
        context="test flag",
        snippet="&dyn_col",
    )
    return Provenance(
        meta=meta,
        tables=[table],
        columns=[col],
        jobs=[job],
        lineage_chain=[lc],
        quality_rules=[qr],
        flags=[flag],
        reconciliation=ReconciliationResult(excel_supplied=False),
    )


def test_provenance_to_dict_has_all_keys():
    d = _sample_provenance().to_dict()
    for key in [
        "meta",
        "tables",
        "columns",
        "jobs",
        "lineage_chain",
        "quality_rules",
        "flags",
        "reconciliation",
    ]:
        assert key in d


def test_table_layer_serialised_as_string():
    d = _sample_provenance().to_dict()
    assert d["tables"][0]["layer"] == "ODS"


def test_job_frequency_serialised_as_string():
    d = _sample_provenance().to_dict()
    assert d["jobs"][0]["frequency"] == "daily"


def test_lineage_step_type_serialised_as_string():
    d = _sample_provenance().to_dict()
    assert d["lineage_chain"][0]["step_type"] == "PROC_SQL"


def test_flag_reason_serialised_as_string():
    d = _sample_provenance().to_dict()
    assert d["flags"][0]["reason"] == "macro_unresolved"


def test_to_json_is_valid():
    prov = _sample_provenance()
    raw = prov.to_json()
    parsed = json.loads(raw)
    assert parsed["meta"]["estate"] == "test"


def test_null_unmappable_reason():
    prov = _sample_provenance()
    prov.lineage_chain[0].unmappable_reason = None
    d = prov.to_dict()
    assert d["lineage_chain"][0]["unmappable_reason"] is None

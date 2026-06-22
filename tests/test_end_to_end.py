"""End-to-end thin slice: sas-parse -> sas-map -> sas-ui, with real lineage."""

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from sas_lineage.parser.cli import main as parse_main
from sas_lineage.schema_mapper.cli import main as map_main
from sas_lineage.web_ui.app import create_app

_JOB = """\
libname RISKODS BASE '/data/ods';
libname MART BASE '/data/mart';

data RISKODS.STG;
    set RISKODS.SRC;
    EXPOSURE = BAL * RATE;
run;

proc sql;
    create table MART.MART as
    select s.EXPOSURE as FINAL_EXP
    from RISKODS.STG s;
quit;
"""


def _build_estate(tmp_path: Path) -> tuple[Path, Path]:
    code = tmp_path / "code"
    logs = tmp_path / "logs"
    code.mkdir()
    logs.mkdir()
    (code / "MART_LOAD_DAILY.sas").write_text(_JOB)
    return code, logs


def test_full_pipeline_emits_and_renders(tmp_path: Path):
    code, logs = _build_estate(tmp_path)
    prov = tmp_path / "provenance.json"
    report = tmp_path / "parse_report.json"

    runner = CliRunner()
    r = runner.invoke(
        parse_main,
        [
            "--code-dir",
            str(code),
            "--log-dir",
            str(logs),
            "--estate",
            "credit-risk",
            "--output",
            str(prov),
            "--report",
            str(report),
        ],
    )
    assert r.exit_code == 0, r.output

    data = json.loads(prov.read_text())
    assert data["columns"], "expected columns to be emitted"
    assert data["lineage_chain"], "expected lineage chain to be emitted"

    # FINAL_EXP is the terminal MART column; its chain must reach BAL/RATE.
    final = next(c for c in data["columns"] if c["name"] == "FINAL_EXP")
    hops = [
        h for h in data["lineage_chain"] if h["mart_column_id"] == final["id"]
    ]
    assert hops, "FINAL_EXP should have a provenance chain"
    assert max(h["chain_order"] for h in hops) >= 2, (
        "chain should span both steps"
    )

    # Tool 2: load + contracts + gaps, with manual owner/domain + quality.
    owners = tmp_path / "owners.csv"
    owners.write_text(
        "job,owner,domain\nMART_LOAD_DAILY,Risk Team,Credit Risk\n"
    )
    params = tmp_path / "params.csv"
    params.write_text(
        "job,rule_name,rule_definition,column_id\n"
        f"MART_LOAD_DAILY,EXP_NON_NEG,FINAL_EXP >= 0,{final['id']}\n"
    )

    db = tmp_path / "lineage.db"
    contracts = tmp_path / "contracts"
    gaps = tmp_path / "gaps.json"
    r = runner.invoke(
        map_main,
        [
            "--provenance",
            str(prov),
            "--db",
            str(db),
            "--contracts-dir",
            str(contracts),
            "--gaps",
            str(gaps),
            "--owners",
            str(owners),
            "--params",
            str(params),
        ],
    )
    assert r.exit_code == 0, r.output

    mart_contract = next(contracts.glob("FDP_MART.yml"))
    contract = yaml.safe_load(mart_contract.read_text())
    assert contract["schema"]["columns"], "contract should carry columns"
    assert contract["owner"] == "Risk Team"
    assert contract["quality"], "quality rules should attach to the contract"

    # Tool 3: the provenance page renders the real chain.
    app = create_app(db)
    client = app.test_client()
    resp = client.get(f"/provenance?col_id={final['id']}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "FINAL_EXP" in body
    assert "mermaid" in body

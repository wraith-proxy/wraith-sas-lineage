"""Defect-class and DI fixtures through the block splitter (eval B1/C1).

Each fixture is synthesised from a defect class documented in
.claude/eval/00-audit.md. Expected block names pin the splitter's
behaviour: quoted semicolons (d02) and datalines bodies (d06) must not
open or close blocks.
"""

from pathlib import Path

import pytest

from sas_lineage.parser.builder import _split_into_blocks

_DEFECTS = Path(__file__).parent / "fixtures" / "defects"
_DI = Path(__file__).parent / "fixtures" / "di"

_EXPECTED = {
    "d01_multiline_statement.sas": ["data_0"],
    "d02_quoted_semicolon.sas": ["data_0", "data_1"],
    "d03_keyword_in_comment.sas": ["SQL_0"],
    "d04_mixed_case_whitespace.sas": ["data_0", "SORT_1"],
    "d05_overbroad_assignment.sas": ["data_0"],
    "d06_datalines_keywords.sas": ["data_0", "data_1", "data_2"],
    "d07_crlf.sas": ["data_0", "SORT_1"],
    # d08: fixed by B10 — starters/terminators also match after ';'.
    "d08_two_statements_one_line.sas": ["SORT_0", "FREQ_1"],
    "d09_hash_object.sas": ["data_0", "data_1"],
    "d10_multi_dataset_merge.sas": ["data_0", "data_1", "data_2"],
}


@pytest.mark.parametrize("name", sorted(_EXPECTED))
def test_defect_fixture_block_structure(name: str):
    blocks = _split_into_blocks((_DEFECTS / name).read_text())
    assert [n for n, _ in blocks] == _EXPECTED[name]


def test_quoted_run_does_not_terminate_block():
    blocks = dict(
        _split_into_blocks((_DEFECTS / "d02_quoted_semicolon.sas").read_text())
    )
    assert "run; is not a terminator" in blocks["data_0"]


def test_datalines_keywords_do_not_start_blocks():
    blocks = dict(
        _split_into_blocks(
            (_DEFECTS / "d06_datalines_keywords.sas").read_text()
        )
    )
    assert "work.bogus" in blocks["data_1"]
    assert not any(n.startswith("FREQ") for n in blocks)


def test_di_job_splits_but_headers_are_stripped():
    """DI boxed headers are comments: current pipeline discards them.

    Pins the C2 precondition from the gap report (B2) — when the header
    extractor lands, it must hook before comment stripping.
    """
    text = (_DI / "di_generated_job.sas").read_text()
    blocks = _split_into_blocks(text)
    names = [n for n, _ in blocks]
    assert "SQL_4" in names
    joined = "".join(b for _, b in blocks)
    assert "Source Table:" not in joined
    assert "Transform:" not in joined
    assert "_OUTPUT1_col2_exp" in joined


def test_di_multi_input_fixture_splits():
    blocks = _split_into_blocks(
        (_DI / "di_multi_input_ambiguity.sas").read_text()
    )
    assert [n for n, _ in blocks] == ["globals_0", "SQL_1", "globals_2"]

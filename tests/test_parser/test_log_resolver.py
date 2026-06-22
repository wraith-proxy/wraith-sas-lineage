"""Tests for log-based macro variable resolution."""

from pathlib import Path

from sas_lineage.parser.log_resolver import LogResolver

_SAMPLE_LOG = """\
NOTE: SAS (r) Proprietary Software Release 9.4
SYMBOLGEN:  Macro variable DT resolves to 20260620
SYMBOLGEN:  Macro variable LIB resolves to RISKODS
MLOGIC(MYMACRO):  %LET SERVER = PROD01
NOTE: DATA statement used.
"""


def test_resolver_parses_symbolgen(tmp_path: Path):
    log = tmp_path / "test.log"
    log.write_text(_SAMPLE_LOG)
    r = LogResolver(log)
    assert r.get("DT") == "20260620"
    assert r.get("LIB") == "RISKODS"


def test_resolver_parses_mlogic(tmp_path: Path):
    log = tmp_path / "test.log"
    log.write_text(_SAMPLE_LOG)
    r = LogResolver(log)
    assert r.get("SERVER") == "PROD01"


def test_resolver_case_insensitive_get(tmp_path: Path):
    log = tmp_path / "test.log"
    log.write_text(_SAMPLE_LOG)
    r = LogResolver(log)
    assert r.get("dt") == r.get("DT")


def test_resolver_resolve_substitutes(tmp_path: Path):
    log = tmp_path / "test.log"
    log.write_text(_SAMPLE_LOG)
    r = LogResolver(log)
    result, ok = r.resolve("&LIB..TABLE")
    assert ok
    assert "RISKODS" in result


def test_resolver_resolve_flags_unresolved(tmp_path: Path):
    log = tmp_path / "test.log"
    log.write_text(_SAMPLE_LOG)
    r = LogResolver(log)
    result, ok = r.resolve("&UNKNOWN_VAR..TABLE")
    assert not ok
    assert "&UNKNOWN_VAR" in result


def test_resolver_no_log():
    r = LogResolver(None)
    assert r.get("ANYTHING") is None
    result, ok = r.resolve("&MACVAR")
    assert not ok


def test_resolver_missing_log(tmp_path: Path):
    r = LogResolver(tmp_path / "nonexistent.log")
    assert r.get("X") is None


def test_resolver_fully_resolved_plain_string(tmp_path: Path):
    log = tmp_path / "test.log"
    log.write_text(_SAMPLE_LOG)
    r = LogResolver(log)
    result, ok = r.resolve("/data/plain/path")
    assert ok
    assert result == "/data/plain/path"

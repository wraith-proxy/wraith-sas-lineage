"""Tests for the directory walker."""

from pathlib import Path

from sas_lineage.parser.walker import walk_pairs


def test_walker_finds_sas_files(tmp_path: Path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    code_dir.mkdir()
    log_dir.mkdir()

    (code_dir / "job_a.sas").write_text("data x; set y; run;")
    (code_dir / "job_b.sas").write_text(
        "proc sql; create table z as select * from w; quit;"
    )

    pairs = list(walk_pairs(code_dir, log_dir))
    names = {p.name for p in pairs}
    assert names == {"job_a", "job_b"}


def test_walker_pairs_log_when_present(tmp_path: Path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    code_dir.mkdir()
    log_dir.mkdir()

    (code_dir / "job_a.sas").write_text("data x; run;")
    (log_dir / "job_a.log").write_text("NOTE: DATA statement used")

    pairs = list(walk_pairs(code_dir, log_dir))
    assert len(pairs) == 1
    assert pairs[0].log_path is not None
    assert pairs[0].log_path.exists()


def test_walker_log_none_when_missing(tmp_path: Path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    code_dir.mkdir()
    log_dir.mkdir()

    (code_dir / "job_no_log.sas").write_text("data x; run;")

    pairs = list(walk_pairs(code_dir, log_dir))
    assert pairs[0].log_path is None


def test_walker_recurses_subdirs(tmp_path: Path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    sub = code_dir / "flows" / "flow01"
    sub.mkdir(parents=True)
    log_dir.mkdir()

    (sub / "deep_job.sas").write_text("proc sort; run;")

    pairs = list(walk_pairs(code_dir, log_dir))
    assert any(p.name == "deep_job" for p in pairs)


def test_walker_empty_dir(tmp_path: Path):
    code_dir = tmp_path / "code"
    log_dir = tmp_path / "logs"
    code_dir.mkdir()
    log_dir.mkdir()

    assert list(walk_pairs(code_dir, log_dir)) == []

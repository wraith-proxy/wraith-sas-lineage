"""Walk the deployed code directory and pair each job with its log."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class JobPair:
    name: str
    code_path: Path
    log_path: Path | None  # None when log is missing


def walk_pairs(code_dir: Path, log_dir: Path) -> Iterator[JobPair]:
    """Yield one JobPair per .sas file found under code_dir."""
    for sas_path in sorted(code_dir.rglob("*.sas")):
        relative = sas_path.relative_to(code_dir)
        log_path = (log_dir / relative).with_suffix(".log")
        yield JobPair(
            name=sas_path.stem,
            code_path=sas_path,
            log_path=log_path if log_path.exists() else None,
        )

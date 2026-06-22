"""
Resolve macro variables from verbose execution logs.

Strategy: logs emitted with MPRINT/SYMBOLGEN/MLOGIC options contain
fully-resolved macro variable values. We prefer log-resolved values
over code literals where they conflict, per the plan. Where no log is
available, %LET / %SYSLPUT statements in the code itself are read as a
best-effort fallback (log always wins on conflict).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sas_lineage.parser import patterns


class LogResolver:
    """Extracts macro variable resolutions from a SAS log file."""

    def __init__(self, log_path: Path | None) -> None:
        self._resolved: dict[str, str] = {}
        self._timestamps: list[datetime] = []
        self._mprint: list[str] = []
        self._datatypes: dict[str, str] = {}
        self._step_notes = 0
        if log_path and log_path.exists():
            self._parse(log_path.read_text(errors="replace"))

    def _parse(self, log_text: str) -> None:
        for line in log_text.splitlines():
            m = patterns.LOG_SYMBOLGEN.search(line)
            if m:
                self._resolved[m.group(1).upper()] = m.group(2).strip()
                continue
            m = patterns.LOG_MLOGIC_VAR.search(line)
            if m:
                self._resolved[m.group(2).upper()] = m.group(3).strip()
                continue
            m = patterns.LOG_MPRINT.match(line)
            if m:
                self._mprint.append(m.group(2).strip())
                continue
            if patterns.LOG_DATA_NOTE.search(
                line
            ) or patterns.LOG_PROC_NOTE.search(line):
                self._step_notes += 1
                continue
            m = patterns.LOG_DATATYPE.search(line)
            if m:
                # PROC CONTENTS variable row: "# NAME Char|Num Len".
                self._datatypes[m.group(2).upper()] = m.group(3).upper()
                continue
            ts = patterns.LOG_TIMESTAMP.search(line)
            if ts:
                stamp = f"{ts.group(1)} {ts.group(2)}"
                fmt = (
                    "%Y-%m-%d %H:%M:%S"
                    if len(ts.group(2)) == 8
                    else "%Y-%m-%d %H:%M"
                )
                self._timestamps.append(datetime.strptime(stamp, fmt))

    def load_code_macros(self, code: str) -> None:
        """Seed %LET / %SYSLPUT literals from code as a fallback.

        Only fills names the log did not already resolve. Log wins.
        """
        for m in patterns.MACRO_LET.finditer(code):
            self._resolved.setdefault(m.group(1).upper(), m.group(2).strip())
        for m in patterns.MACRO_SYSLPUT.finditer(code):
            self._resolved.setdefault(m.group(1).upper(), m.group(2).strip())

    def run_timestamps(self) -> list[datetime]:
        """Return run timestamps found in the log (for cadence inference)."""
        return self._timestamps

    def log_step_count(self) -> int:
        """Number of DATA/PROC step-completion NOTEs seen in the log."""
        return self._step_notes

    def mprint_statements(self) -> list[str]:
        """Return fully-resolved statement text captured from MPRINT lines."""
        return self._mprint

    def datatype(self, column_name: str) -> str | None:
        """Return the logged SAS datatype (CHAR/NUM) for a column, if known."""
        return self._datatypes.get(column_name.upper())

    def resolve(self, value: str) -> tuple[str, bool]:
        """
        Replace &macvar references in value using log-resolved table.

        Returns (resolved_value, fully_resolved).
        fully_resolved is False if any &macvar remains after substitution.
        """

        def _sub(match: re.Match) -> str:
            key = match.group(1).upper()
            return self._resolved.get(key, match.group(0))

        result = patterns.MACRO_VAR_REF.sub(_sub, value)
        fully_resolved = "&" not in result
        return result, fully_resolved

    def get(self, name: str) -> str | None:
        return self._resolved.get(name.upper())

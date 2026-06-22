"""
Freshness / SLA inference (single source of truth).

Strategy: job name tokens first, then log cadence from run timestamps. The
parser owns this because only the parser sees the logs; the inferred frequency
travels in provenance.json and Tool 2 merely carries it into the contract.
Calendar exceptions (bank holidays) noted as best-effort only.
"""

from __future__ import annotations

import re
from datetime import datetime

_FREQ_PATTERNS = [
    (
        re.compile(r"(?:^|[_\W])(?:daily|dly)(?:[_\W]|$)", re.IGNORECASE),
        "daily",
    ),
    (
        re.compile(r"(?:^|[_\W])(?:weekly|wkly)(?:[_\W]|$)", re.IGNORECASE),
        "weekly",
    ),
    (
        re.compile(
            r"(?:^|[_\W])(?:monthly|mthly|mth)(?:[_\W]|$)", re.IGNORECASE
        ),
        "monthly",
    ),
    (
        re.compile(
            r"(?:^|[_\W])(?:quarterly|qtrly|qtr)(?:[_\W]|$)", re.IGNORECASE
        ),
        "quarterly",
    ),
    (
        re.compile(
            r"(?:^|[_\W])(?:annual|yearly|yr)(?:[_\W]|$)", re.IGNORECASE
        ),
        "annual",
    ),
]


def infer_from_name(job_name: str) -> tuple[str | None, list[str]]:
    """Return (frequency_label, evidence) from job name tokens."""
    for pattern, label in _FREQ_PATTERNS:
        if pattern.search(job_name):
            return label, [f"name_token:{label}"]
    return None, []


def infer_from_log_timestamps(
    timestamps: list[datetime],
) -> tuple[str | None, list[str]]:
    """
    Infer run cadence from a list of log execution timestamps.

    Requires at least 3 timestamps for a confident inference.
    Returns (frequency_label, evidence).
    """
    if len(timestamps) < 3:
        return None, []

    timestamps = sorted(timestamps)
    deltas = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
    ]
    median_seconds = sorted(deltas)[len(deltas) // 2]

    thresholds = [
        (86400 * 1.5, "daily"),
        (86400 * 8, "weekly"),
        (86400 * 35, "monthly"),
        (86400 * 100, "quarterly"),
        (86400 * 400, "annual"),
    ]
    for threshold, label in thresholds:
        if median_seconds <= threshold:
            return label, [f"log_cadence:{label}"]
    return None, ["log_cadence:irregular"]

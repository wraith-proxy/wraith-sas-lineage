"""Tests for freshness / SLA inference."""

from datetime import datetime, timedelta

from sas_lineage.parser.freshness import (
    infer_from_log_timestamps,
    infer_from_name,
)


def test_daily_from_name():
    freq, evidence = infer_from_name("SALES_LOAD_DAILY")
    assert freq == "daily"
    assert evidence


def test_weekly_from_name():
    freq, _ = infer_from_name("ORDERS_WEEKLY_AGG")
    assert freq == "weekly"


def test_monthly_from_name():
    freq, _ = infer_from_name("REPORT_MTHLY")
    assert freq == "monthly"


def test_quarterly_from_name():
    freq, _ = infer_from_name("QTR_SUMMARY")
    assert freq == "quarterly"


def test_annual_from_name():
    freq, _ = infer_from_name("YEARLY_ROLLUP")
    assert freq == "annual"


def test_no_match_returns_none():
    freq, evidence = infer_from_name("UNKNOWN_JOB")
    assert freq is None
    assert evidence == []


def test_log_timestamps_daily():
    base = datetime(2026, 1, 1)
    ts = [base + timedelta(days=i) for i in range(5)]
    freq, evidence = infer_from_log_timestamps(ts)
    assert freq == "daily"
    assert evidence


def test_log_timestamps_weekly():
    base = datetime(2026, 1, 1)
    ts = [base + timedelta(weeks=i) for i in range(5)]
    freq, evidence = infer_from_log_timestamps(ts)
    assert freq == "weekly"


def test_log_timestamps_too_few():
    ts = [datetime(2026, 1, 1), datetime(2026, 1, 2)]
    freq, evidence = infer_from_log_timestamps(ts)
    assert freq is None
    assert evidence == []


def test_log_timestamps_monthly():
    base = datetime(2026, 1, 1)
    ts = [base + timedelta(days=30 * i) for i in range(5)]
    freq, _ = infer_from_log_timestamps(ts)
    assert freq == "monthly"

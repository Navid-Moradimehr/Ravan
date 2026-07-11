from datetime import datetime, timezone

from services.common.clock_quality import clock_quality_issue


def test_clock_quality_accepts_timestamp_within_bound():
    now = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    assert clock_quality_issue("2026-07-11T11:59:30Z", max_offset_seconds=60, now=now) is None


def test_clock_quality_reports_old_and_future_timestamps():
    now = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    old = clock_quality_issue("2026-07-11T11:58:00Z", max_offset_seconds=60, now=now)
    future = clock_quality_issue("2026-07-11T12:02:00Z", max_offset_seconds=60, now=now)
    assert old is not None and "behind" in old
    assert future is not None and "ahead" in future


def test_clock_quality_reports_invalid_timestamp():
    assert "not a valid" in clock_quality_issue("not-a-time", max_offset_seconds=60)

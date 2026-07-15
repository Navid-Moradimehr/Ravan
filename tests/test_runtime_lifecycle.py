from datetime import datetime, timezone

from services.common.runtime_lifecycle import classify_source_lifecycle, enrich_source_health


NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def test_active_source_is_running_before_stale_threshold():
    result = classify_source_lifecycle("connected", "2026-07-15T11:59:50+00:00", now=NOW, expected_interval_seconds=10)
    assert result["lifecycle"] == "running"
    assert result["stale"] is False


def test_missing_events_are_classified_as_unplanned_interruption():
    result = classify_source_lifecycle("connected", "2026-07-15T11:59:20+00:00", now=NOW, expected_interval_seconds=10)
    assert result["lifecycle"] == "interrupted"
    assert result["planned"] is False


def test_planned_shutdown_is_not_reported_as_an_incident():
    result = classify_source_lifecycle("stopped", "2026-07-15T11:59:20+00:00", now=NOW, planned=True)
    assert result["lifecycle"] == "planned_downtime"
    assert result["planned"] is True


def test_reconnecting_source_is_recovering_even_before_stale_threshold():
    result = classify_source_lifecycle("reconnecting", "2026-07-15T11:59:55+00:00", now=NOW, expected_interval_seconds=10)
    assert result["lifecycle"] == "recovering"


def test_enrichment_preserves_existing_source_fields():
    result = enrich_source_health({"connection_id": "c1", "state": "connected", "last_success_at": "2026-07-15T11:59:59+00:00"}, now=NOW)
    assert result["connection_id"] == "c1"
    assert result["lifecycle"] == "running"


def test_missing_success_timestamp_does_not_create_false_interruption():
    result = classify_source_lifecycle("connected", None, now=NOW, expected_interval_seconds=10)
    assert result["lifecycle"] == "running"
    assert result["stale"] is False
    assert result["staleness_known"] is False

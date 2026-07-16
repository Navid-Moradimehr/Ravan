from datetime import datetime, timedelta, timezone

from services.common.operational_briefing import (
    build_briefing_context,
    compact_report_memory,
    deterministic_briefing,
    select_report_evidence,
    validate_briefing,
)


def test_evidence_selection_covers_streams_and_prioritizes_severity():
    events = [
        {"event_id": "n1", "asset_id": "pump-1", "tag": "temp", "severity": "normal"},
        {"event_id": "w1", "asset_id": "pump-1", "tag": "temp", "severity": "warning"},
        {"event_id": "c1", "asset_id": "pump-2", "tag": "vibration", "severity": "critical"},
    ]
    selected = select_report_evidence(events, max_events=2)
    assert [event["event_id"] for event in selected] == ["c1", "w1"]


def test_short_memory_is_site_supplied_bounded_and_expires_old_reports():
    now = datetime.now(timezone.utc)
    reports = [
        {"job_id": "recent", "updated_at": now, "report_type": "scheduled", "result": {"briefing": {"headline": "Current", "situation_status": "normal", "affected_assets": []}}},
        {"job_id": "old", "updated_at": now - timedelta(days=2), "report_type": "scheduled", "result": {"briefing": {"headline": "Old", "situation_status": "normal", "affected_assets": []}}},
    ]
    assert [item["report_id"] for item in compact_report_memory(reports)] == ["recent"]


def test_deterministic_briefing_is_valid_and_grounded():
    context = build_briefing_context(
        [{"event_id": "c1", "site_id": "plant-a", "asset_id": "pump-2", "tag": "vibration", "severity": "critical"}],
        report_type="anomaly",
        site_id="plant-a",
    )
    briefing = deterministic_briefing(context, "provider unavailable")
    valid, errors, parsed = validate_briefing(briefing)
    assert valid is True
    assert errors == []
    assert parsed["situation_status"] == "critical"
    assert parsed["evidence_references"] == ["c1"]

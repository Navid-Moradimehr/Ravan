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


def test_deterministic_briefing_exposes_recent_short_memory():
    context = build_briefing_context(
        [{"event_id": "c2", "site_id": "plant-a", "asset_id": "pump-3", "tag": "temperature", "severity": "warning"}],
        report_type="anomaly",
        site_id="plant-a",
        previous_reports=[
            {"job_id": "r3", "updated_at": datetime.now(timezone.utc), "report_type": "anomaly", "result": {"briefing": {"headline": "Pump-3 warning continues", "situation_status": "attention", "active_issues": [{"issue_id": "i3"}], "affected_assets": ["pump-3"]}}},
            {"job_id": "r2", "updated_at": datetime.now(timezone.utc) - timedelta(hours=1), "report_type": "anomaly", "result": {"briefing": {"headline": "Pump-2 warning", "situation_status": "attention", "active_issues": [{"issue_id": "i2"}], "affected_assets": ["pump-2"]}}},
            {"job_id": "r1", "updated_at": datetime.now(timezone.utc) - timedelta(hours=2), "report_type": "scheduled", "result": {"briefing": {"headline": "All clear", "situation_status": "normal", "active_issues": [], "affected_assets": []}}},
        ],
    )
    briefing = deterministic_briefing(context, "provider unavailable")
    assert briefing["continuity"]["memory_count"] == 3
    assert [item["report_id"] for item in briefing["continuity"]["short_memory"]] == ["r3", "r2", "r1"]
    assert briefing["continuity"]["short_memory"][0]["headline"] == "Pump-3 warning continues"

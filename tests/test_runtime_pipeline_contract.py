from __future__ import annotations

from services.common.runtime_event import RuntimeEventRecord, RollingWindowState
from services.processor.runtime_pipeline import build_runtime_event_payload, enrich_runtime_event


def test_enrich_runtime_event_updates_record_and_result() -> None:
    event = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-1",
            "source_protocol": "mqtt",
            "source_id": "site-a/mqtt/pump-1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 72.0,
            "quality": "good",
            "unit": "c",
            "site": "Factory-A",
            "line": "Line-1",
            "ts_source": "2026-06-19T10:00:00+00:00",
        }
    )

    result = enrich_runtime_event(
        event,
        temperature_avg_c=71.5,
        vibration_avg_mm_s=0.0,
        window_size=4,
    )

    assert result.window_size == 4
    assert result.anomaly_score >= 0.35
    assert event.severity == result.severity
    assert event.window_size == 4
    assert event.temperature_avg_c == 71.5


def test_build_runtime_event_payload_includes_shared_fields() -> None:
    event = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-2",
            "source_protocol": "opcua",
            "source_id": "site-a/opcua/pump-2",
            "asset_id": "Pump-02",
            "tag": "Vibration",
            "value": 7.8,
            "quality": "good",
            "unit": "mm/s",
            "site": "Factory-A",
            "line": "Line-1",
            "ts_source": "2026-06-19T10:00:01+00:00",
        }
    )

    payload = build_runtime_event_payload(
        event,
        temperature_avg_c=55.0,
        vibration_avg_mm_s=7.8,
        window_size=2,
    )

    assert payload["window_size"] == 2
    assert payload["severity"] in {"normal", "warning", "critical"}
    assert payload["temperature_avg_c"] == 55.0
    assert payload["vibration_avg_mm_s"] == 7.8
    assert payload["asset_id"] == "Pump-02"


def test_rolling_window_state_retains_bounded_size() -> None:
    state = RollingWindowState(maxlen=2)
    first = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-1",
            "source_protocol": "mqtt",
            "source_id": "site-a/mqtt/pump-1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 50.0,
            "quality": "good",
            "unit": "c",
            "site": "Factory-A",
            "line": "Line-1",
            "ts_source": "2026-06-19T10:00:00+00:00",
        }
    )
    second = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-2",
            "source_protocol": "mqtt",
            "source_id": "site-a/mqtt/pump-1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 60.0,
            "quality": "good",
            "unit": "c",
            "site": "Factory-A",
            "line": "Line-1",
            "ts_source": "2026-06-19T10:00:01+00:00",
        }
    )
    third = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-3",
            "source_protocol": "mqtt",
            "source_id": "site-a/mqtt/pump-1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 70.0,
            "quality": "good",
            "unit": "c",
            "site": "Factory-A",
            "line": "Line-1",
            "ts_source": "2026-06-19T10:00:02+00:00",
        }
    )

    avg_temp, avg_vibration, size = state.append(first)
    assert avg_temp == 50.0
    assert avg_vibration == 0.0
    assert size == 1

    avg_temp, avg_vibration, size = state.append(second)
    assert avg_temp == 55.0
    assert avg_vibration == 0.0
    assert size == 2

    avg_temp, avg_vibration, size = state.append(third)
    assert avg_temp == 65.0
    assert avg_vibration == 0.0
    assert size == 2

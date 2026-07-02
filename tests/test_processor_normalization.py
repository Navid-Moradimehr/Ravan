from __future__ import annotations

from services.common.runtime_event import RollingWindowState, RuntimeEventRecord
from services.common.stream_scope import stream_partition_key
from services.edge_ingest.model import IndustrialEvent, to_json_bytes
from services.processor.runtime_processor import normalize_runtime_event, score_event


def test_processor_accepts_industrial_envelope() -> None:
    event = normalize_runtime_event(
        {
            "event_id": "evt-1",
            "source_protocol": "modbus",
            "asset_id": "Pump-03",
            "tag": "Vibration",
            "value": 9.2,
            "quality": "good",
            "site": "demo-site",
            "ts_source": "2026-06-19T10:00:00+00:00",
            "schema_version": 1,
        }
    )

    assert event["device_id"] == "Pump-03"
    assert event["vibration_mm_s"] == 9.2
    assert score_event(event, temperature_avg=48, vibration_avg=6) >= 0.45


def test_processor_keeps_legacy_event_shape() -> None:
    legacy = {"device_id": "device-001", "temperature_c": 40, "vibration_mm_s": 2, "pressure_bar": 6}

    assert normalize_runtime_event(legacy) is legacy


def test_runtime_record_preserves_partition_key_and_serialization() -> None:
    record = RuntimeEventRecord.from_industrial_event(
        IndustrialEvent(
            source_protocol="modbus",
            source_id="site-a/line-1/plc-01",
            asset_id="Pump-03",
            tag="Temperature",
            value=66.2,
            quality="good",
            unit="c",
            site="Factory-A",
            line="Line-1",
            ts_source="2026-06-19T10:00:00+00:00",
            schema_version=1,
        )
    )
    record.mark_processed(window_size=3, temperature_avg_c=61.0, vibration_avg_mm_s=2.0, anomaly_score=0.8, severity="critical")

    assert record.partition_key() == stream_partition_key(record)
    encoded = to_json_bytes(record)
    assert b'"severity":"critical"' in encoded
    assert b'"window_size":3' in encoded


def test_rolling_window_state_uses_rolling_sums() -> None:
    state = RollingWindowState(maxlen=2)
    first = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-1",
            "source_protocol": "mqtt",
            "source_id": "site-a/mqtt/pump-1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 55.0,
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
            "value": 65.0,
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
            "value": 75.0,
            "quality": "good",
            "unit": "c",
            "site": "Factory-A",
            "line": "Line-1",
            "ts_source": "2026-06-19T10:00:02+00:00",
        }
    )

    temperature_avg, vibration_avg, size = state.append(first)
    assert temperature_avg == 55.0
    assert vibration_avg == 0.0
    assert size == 1

    temperature_avg, vibration_avg, size = state.append(second)
    assert temperature_avg == 60.0
    assert vibration_avg == 0.0
    assert size == 2

    temperature_avg, vibration_avg, size = state.append(third)
    assert temperature_avg == 70.0
    assert vibration_avg == 0.0
    assert size == 2

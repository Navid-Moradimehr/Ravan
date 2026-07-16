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


def test_runtime_record_preserves_composite_sensor_frame() -> None:
    record = RuntimeEventRecord.from_raw_mapping(
        {
            "event_id": "evt-composite-1",
            "device_id": "compressor-07",
            "source_protocol": "simulator",
            "site_id": "plant-a",
            "timestamp": "2026-07-16T10:00:00+00:00",
            "temperature_c": 73.4,
            "vibration_mm_s": 4.8,
            "pressure_bar": 8.2,
        }
    )

    assert record.asset_id == "compressor-07"
    assert record.source_id == "compressor-07"
    assert record.device_id == "compressor-07"
    assert record.tag == "__composite__"
    assert record.value_type == "composite"
    assert record.timestamp == "2026-07-16T10:00:00+00:00"
    assert record.temperature_c == 73.4
    assert record.vibration_mm_s == 4.8
    assert record.pressure_bar == 8.2


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


def test_runtime_processor_persist_gate_default_on(monkeypatch) -> None:
    from services.processor import runtime_processor as rp

    assert rp.should_persist_processed() is True
    monkeypatch.setenv("RUNTIME_PERSIST_PROCESSED_EVENTS", "0")
    assert rp.should_persist_processed() is False
    monkeypatch.setenv("RUNTIME_PERSIST_PROCESSED_EVENTS", "false")
    assert rp.should_persist_processed() is False


def test_runtime_processor_flush_skips_historian_when_gate_off() -> None:
    """With the persist gate off, historian writes are skipped but offsets commit."""
    from services.processor import runtime_processor as rp

    batch_calls: list[list[dict]] = []
    single_calls: list[dict] = []
    committed: list[list] = []

    buffer = [{"event_id": "e1"}, {"event_id": "e2"}]
    offsets = [("iot.raw", 0, 4), ("iot.raw", 0, 5)]

    rp._flush_processed_batch(
        buffer,
        offsets,
        force=True,
        db_batch_size=1024,
        db_flush_seconds=1.0,
        last_db_flush=0.0,
        persist_processed=False,
        insert_batch=batch_calls.append,
        insert_single=single_calls.append,
        commit_offsets=committed.append,
    )

    assert batch_calls == []
    assert single_calls == []
    # Offsets are still committed so the consumer advances.
    assert len(committed) == 1
    # Committed offsets are offset+1 (next position).
    assert committed[0][0].offset == 5
    assert committed[0][1].offset == 6
    assert buffer == []
    assert offsets == []


def test_runtime_processor_flush_writes_historian_when_gate_on() -> None:
    """With the persist gate on, the historian batch write runs and offsets commit."""
    from services.processor import runtime_processor as rp

    batch_calls: list[list[dict]] = []
    committed: list[list] = []

    buffer = [{"event_id": "e1"}]
    offsets = [("iot.raw", 0, 9)]

    rp._flush_processed_batch(
        buffer,
        offsets,
        force=True,
        db_batch_size=1024,
        db_flush_seconds=1.0,
        last_db_flush=0.0,
        persist_processed=True,
        insert_batch=batch_calls.append,
        insert_single=lambda e: None,
        commit_offsets=committed.append,
    )

    assert len(batch_calls) == 1
    assert batch_calls[0] == [{"event_id": "e1"}]
    assert len(committed) == 1
    assert committed[0][0].offset == 10


def test_runtime_processor_flush_holds_when_below_threshold() -> None:
    """Below batch size and within flush interval, nothing is flushed."""
    from services.processor import runtime_processor as rp

    batch_calls: list[list[dict]] = []
    committed: list[list] = []

    buffer = [{"event_id": "e1"}]
    offsets = [("iot.raw", 0, 0)]

    import time as _time

    new_flush = rp._flush_processed_batch(
        buffer,
        offsets,
        force=False,
        db_batch_size=1024,
        db_flush_seconds=1.0,
        last_db_flush=_time.monotonic(),
        persist_processed=True,
        insert_batch=batch_calls.append,
        insert_single=lambda e: None,
        commit_offsets=committed.append,
    )

    assert batch_calls == []
    assert committed == []
    assert buffer == [{"event_id": "e1"}]
    assert new_flush is not None

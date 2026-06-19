from __future__ import annotations

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

from __future__ import annotations

import json

from services.edge_ingest.main import to_legacy_iot_event
from services.edge_ingest.model import IndustrialEvent, to_json_bytes, validate_event, utc_now


def test_valid_industrial_event_passes_validation() -> None:
    payload = {
        "source_protocol": "mqtt",
        "source_id": "factory/line-01/Pump-01/Temperature",
        "asset_id": "Pump-01",
        "tag": "Temperature",
        "value": 51.2,
        "quality": "good",
        "unit": "c",
        "ts_source": utc_now(),
    }

    event, dlq = validate_event(payload)

    assert dlq is None
    assert event is not None
    assert event.source_protocol == "mqtt"
    assert event.asset_id == "Pump-01"
    assert event.schema_version == 1


def test_invalid_industrial_event_routes_to_dlq() -> None:
    event, dlq = validate_event(
        {
            "source_protocol": "mqtt",
            "source_id": "factory/bad",
            "asset_id": "",
            "tag": "",
            "value": 12,
            "quality": "good",
            "ts_source": utc_now(),
        }
    )

    assert event is None
    assert dlq is not None
    assert dlq.source_protocol == "mqtt"
    assert "must not be empty" in dlq.error


def test_industrial_event_maps_to_legacy_processor_shape() -> None:
    event = IndustrialEvent(
        source_protocol="opcua",
        source_id="ns=2;s=Pump-01.Temperature",
        asset_id="Pump-01",
        tag="Temperature",
        value=72.5,
        quality="good",
        unit="c",
        ts_source=utc_now(),
    )

    legacy = to_legacy_iot_event(event)

    assert legacy["device_id"] == "Pump-01"
    assert legacy["temperature_c"] == 72.5
    assert legacy["vibration_mm_s"] == 0.0
    json.dumps(legacy)


def test_model_serializes_to_compact_json_bytes() -> None:
    event = IndustrialEvent(
        source_protocol="mqtt",
        source_id="factory/line-01/Pump-01/Temperature",
        asset_id="Pump-01",
        tag="Temperature",
        value=51.2,
        quality="good",
        unit="c",
        ts_source=utc_now(),
    )

    payload = to_json_bytes(event)

    assert isinstance(payload, bytes)
    assert b"Pump-01" in payload

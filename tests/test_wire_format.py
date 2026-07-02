from __future__ import annotations

from services.common.wire_format import deserialize_payload, serialize_payload


def test_msgpack_roundtrip_smaller_than_json():
    payload = {
        "event_id": "evt-1",
        "source_protocol": "mqtt",
        "source_id": "site-a/mqtt/pump-1",
        "asset_id": "Pump-1",
        "tag": "Temperature",
        "value": 55.1,
        "quality": "good",
        "unit": "c",
        "site": "Factory-A",
        "line": "Line-1",
        "ts_source": "2026-07-01T00:00:00Z",
        "schema_version": 1,
    }

    json_bytes = serialize_payload(payload, wire_format="json")
    msgpack_bytes = serialize_payload(payload, wire_format="msgpack")

    assert deserialize_payload(msgpack_bytes, wire_format="msgpack") == payload
    assert len(msgpack_bytes) <= len(json_bytes)


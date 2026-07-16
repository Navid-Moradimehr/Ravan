from __future__ import annotations

from services.edge_ingest.rest_support import deep_get, event_from_record, records_from_response


def test_rest_json_paths_and_record_mapping():
    payload = {"data": {"items": [{"device": {"id": "sensor-7"}, "metric": "temperature", "reading": 21.5}]}}
    records = records_from_response(payload, "data.items")
    event = event_from_record(
        records[0],
        field_paths={"source_id": "device.id", "tag": "metric", "value": "reading", "asset_id": "device.id"},
        connection_id="conn-rest",
        site_id="plant-a",
        source_id="api",
    )
    assert deep_get(payload, "data.items.0.reading") == 21.5
    assert event["source_id"] == "sensor-7"
    assert event["asset_id"] == "sensor-7"
    assert event["value"] == 21.5
    assert event["quality"] == "good"
    assert event["site"] == "plant-a"
    assert event["unit"] == ""


def test_rest_response_without_records_is_safe():
    assert records_from_response({"status": "ok"}, "data.items") == []

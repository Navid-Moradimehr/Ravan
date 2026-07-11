from __future__ import annotations

import json

from services.edge_ingest import source_health
from services.edge_ingest.source_health import mark_source, mark_source_success, snapshot
from services.edge_ingest.settings import SourceRuntime


def test_source_health_tracks_latest_state():
    source_health._states.clear()
    mark_source("conn-1", "mqtt", "plant-a", "error", "offline")
    assert snapshot()[-1]["state"] == "error"
    mark_source_success("conn-1", "mqtt", "plant-a")
    assert snapshot()[-1]["state"] == "connected"


def test_source_health_persists_only_state_transitions(tmp_path, monkeypatch):
    source_health._states.clear()
    monkeypatch.setattr(source_health, "HISTORY_PATH", tmp_path / "source-health.json")
    mark_source("conn-history", "opcua", "plant-a", "connected")
    mark_source("conn-history", "opcua", "plant-a", "connected")
    mark_source("conn-history", "opcua", "plant-a", "error", "offline")
    payload = json.loads((tmp_path / "source-health.json").read_text())
    assert len(payload) == 2
    assert source_health.history()[-1]["state"] == "error"


def test_mapping_results_survive_health_updates():
    source_health._states.clear()
    runtime = SourceRuntime(
        connection_id="conn-map",
        source_protocol="opcua",
        site_id="plant-a",
        source_id="pump-01",
        mappings=(
            {"source_field": "pump-01", "asset_id": "Pump-01", "tag": "Temperature"},
        ),
    )
    payload, matched, source_field = runtime.map_event_with_status({"source_id": "pump-01", "value": 42.0, "tag": "Temperature", "asset_id": "Pump-01"})
    assert matched is True
    assert source_field == "pump-01"
    assert payload["asset_id"] == "Pump-01"
    source_health.mark_mapping_result("conn-map", "opcua", "plant-a", matched=matched, source_field=source_field)
    mark_source_success("conn-map", "opcua", "plant-a")
    state = snapshot()[-1]
    assert state["mapping_seen"] == 1
    assert state["mapping_matched"] == 1
    assert state["mapping_missed"] == 0
    assert state["state"] == "connected"


def test_mapping_miss_is_tracked_without_changing_payload():
    source_health._states.clear()
    runtime = SourceRuntime(
        connection_id="conn-miss",
        source_protocol="mqtt",
        site_id="plant-a",
        source_id="topic/a",
        mappings=(
            {"source_field": "topic/b", "asset_id": "Pump-02", "tag": "Pressure"},
        ),
    )
    payload, matched, source_field = runtime.map_event_with_status({"source_id": "topic/a", "value": 12.5, "tag": "Temperature", "asset_id": "Pump-01"})
    assert matched is False
    assert source_field == ""
    assert payload["asset_id"] == "Pump-01"
    source_health.mark_mapping_result("conn-miss", "mqtt", "plant-a", matched=matched, source_field=source_field)
    state = snapshot()[-1]
    assert state["mapping_seen"] == 1
    assert state["mapping_matched"] == 0
    assert state["mapping_missed"] == 1

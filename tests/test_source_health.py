from __future__ import annotations

import json

from services.edge_ingest import source_health
from services.edge_ingest.source_health import mark_source, mark_source_success, snapshot


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

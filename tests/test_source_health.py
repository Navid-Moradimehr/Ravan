from __future__ import annotations

from services.edge_ingest.source_health import mark_source, mark_source_success, snapshot


def test_source_health_tracks_latest_state():
    mark_source("conn-1", "mqtt", "plant-a", "error", "offline")
    assert snapshot()[-1]["state"] == "error"
    mark_source_success("conn-1", "mqtt", "plant-a")
    assert snapshot()[-1]["state"] == "connected"

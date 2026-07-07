from __future__ import annotations

from fastapi.testclient import TestClient


def test_operational_memory_snapshot_exposes_existing_surfaces(tmp_path, monkeypatch) -> None:
    from services.common.operational_memory import build_operational_memory_snapshot

    snapshot = build_operational_memory_snapshot()

    assert snapshot["plane"] == "operational-memory"
    assert snapshot["sections"]
    assert snapshot["alerts"]["statistics"]["total_alerts"] >= 0
    assert isinstance(snapshot["annotations"], list)
    assert snapshot["shifts"]
    assert snapshot["reports"]["templates"] is not None
    assert "work_orders" in snapshot["contracts"]["not_yet_native"]
    assert snapshot["contracts"]["read_only"] is True


def test_operational_memory_api_route_returns_snapshot() -> None:
    from services.api_service.main import app

    client = TestClient(app)
    response = client.get("/api/v1/metadata/operational")

    assert response.status_code == 200
    body = response.json()
    assert body["plane"] == "operational-memory"
    assert body["contracts"]["operational_memory_is_logical"] is True


from __future__ import annotations

from fastapi.testclient import TestClient


def test_governance_snapshot_reports_registry_lifecycle() -> None:
    from services.common.governance_plane import build_governance_snapshot

    snapshot = build_governance_snapshot()

    assert snapshot["read_only"] is True
    assert snapshot["schema_count"] >= 1
    assert snapshot["model_roles"]
    assert snapshot["prompt_count"] >= 1
    assert snapshot["dataset_count"] >= 1
    assert snapshot["contracts"]["schema_governance"] is True


def test_governance_route_returns_snapshot() -> None:
    from services.api_service.main import app

    client = TestClient(app)
    response = client.get("/api/v1/metadata/governance")

    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["contracts"]["model_governance"] is True

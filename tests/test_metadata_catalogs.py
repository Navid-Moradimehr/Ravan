from __future__ import annotations

from fastapi.testclient import TestClient


def test_asset_registry_snapshot_aggregates_asset_hierarchy() -> None:
    from services.common.asset_registry import build_asset_registry_snapshot

    snapshot = build_asset_registry_snapshot()

    assert snapshot["contracts"]["logical_registry"] is True
    assert snapshot["entry_count"] > 0
    assert snapshot["by_type"]["site"] >= 1
    assert any(node_type not in {"site"} for node_type in snapshot["by_type"])
    assert snapshot["tree"]
    assert snapshot["entries"]


def test_event_catalog_snapshot_lists_canonical_topics() -> None:
    from services.common.event_catalog import build_event_catalog_snapshot

    snapshot = build_event_catalog_snapshot()

    topic_names = {entry["topic"] for entry in snapshot["canonical_topics"]}
    assert "industrial.normalized" in topic_names
    assert "iot.processed" in topic_names
    assert snapshot["counts"]["canonical_topics"] >= 6
    assert "industrial" in snapshot["counts"]["categories"]
    assert "ai" in snapshot["counts"]["categories"]
    assert snapshot["counts"]["ai_event_contracts"] >= 3
    assert snapshot["ai_event_contracts"][0]["event_type"] == "ai.summary.generated"
    assert snapshot["project_topics"]


def test_metadata_asset_and_event_routes_return_snapshots(tmp_path, monkeypatch) -> None:
    from services.api_service.main import app

    monkeypatch.setenv("SEMANTIC_STORE_PATH", str(tmp_path / "semantic-store.json"))
    client = TestClient(app)

    asset_response = client.get("/api/v1/metadata/assets")
    event_response = client.get("/api/v1/metadata/events")

    assert asset_response.status_code == 200
    assert event_response.status_code == 200
    assert asset_response.json()["contracts"]["logical_registry"] is True
    assert event_response.json()["contracts"]["logical_catalog"] is True

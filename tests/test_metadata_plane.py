from __future__ import annotations

from fastapi.testclient import TestClient


def test_metadata_plane_snapshot_aggregates_existing_registries(tmp_path) -> None:
    from services.common.metadata_plane import build_metadata_plane_snapshot

    snapshot = build_metadata_plane_snapshot(
        semantic_store_path=tmp_path / "semantic-store.json",
        asset_config="config/assets.yaml",
    )

    assert snapshot["plane"] == "logical-metadata-plane"
    assert snapshot["ownership"]["platform_core"]
    assert snapshot["ownership"]["user_owned"]

    memory_layer_names = {layer["name"] for layer in snapshot["memory_layers"]}
    assert {"Historical Memory", "Semantic Memory", "Operational Memory"} <= memory_layer_names

    registries = snapshot["registries"]
    assert registries["asset_registry"]["entry_count"] > 0
    assert registries["schemas"]
    assert any(binding["role"] == "summarization" for binding in registries["models"]["roles"])
    assert registries["prompts"]
    assert registries["datasets"]
    assert snapshot["planes"]["data"]["name"] == "Data Plane"
    assert snapshot["planes"]["control"]["name"] == "Control Plane"
    assert snapshot["planes"]["intelligence"]["name"] == "Intelligence Plane"
    assert snapshot["dataset_builder"]["contracts"]["logical_contract"] is True

    assert snapshot["catalogs"]["semantic_core"]["platform_primitives"]
    assert snapshot["catalogs"]["retrieval"]["sources"]
    assert snapshot["catalogs"]["event_catalog"]["canonical_topics"]
    assert snapshot["semantic_store"]["ontology_pack_count"] >= 1
    assert snapshot["operational_memory"]["alerts"]["statistics"]["total_alerts"] >= 0
    assert snapshot["contracts"]["metadata_is_read_only"] is True


def test_metadata_plane_api_route_returns_snapshot(tmp_path, monkeypatch) -> None:
    from services.api_service.main import app

    monkeypatch.setenv("SEMANTIC_STORE_PATH", str(tmp_path / "semantic-store.json"))
    client = TestClient(app)

    response = client.get("/api/v1/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["plane"] == "logical-metadata-plane"
    assert body["semantic_store"]["lineage_count"] >= 0
    assert body["contracts"]["metadata_is_logical"] is True
    assert body["dataset_builder"]["contracts"]["logical_contract"] is True

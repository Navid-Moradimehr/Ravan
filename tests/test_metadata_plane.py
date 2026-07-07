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
    assert registries["schemas"]
    assert any(binding["role"] == "summarization" for binding in registries["models"]["roles"])
    assert registries["prompts"]
    assert registries["datasets"]

    assert snapshot["catalogs"]["semantic_core"]["platform_primitives"]
    assert snapshot["catalogs"]["retrieval"]["sources"]
    assert snapshot["semantic_store"]["ontology_pack_count"] >= 1
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


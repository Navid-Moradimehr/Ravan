from __future__ import annotations

from fastapi.testclient import TestClient


def test_semantic_routes_return_graph_and_core_catalog() -> None:
    from services.api_service.main import app

    client = TestClient(app)

    core = client.get("/api/v1/semantic/core")
    graph = client.get("/api/v1/semantic/graph")
    search = client.get("/api/v1/semantic/graph/search", params={"q": "pump temperature", "limit": 5})
    packs = client.get("/api/v1/semantic/ontology-packs")

    assert core.status_code == 200
    assert graph.status_code == 200
    assert search.status_code == 200
    assert packs.status_code == 200
    core_json = core.json()
    graph_json = graph.json()
    search_json = search.json()
    packs_json = packs.json()
    assert "Entity" in core_json["platform_primitives"]
    assert graph_json["counts"]["entities"] > 0
    assert search_json["entities"]
    assert packs_json["ontology_packs"]


def test_semantic_write_routes_accept_updates(tmp_path, monkeypatch) -> None:
    from services.api_service.main import app

    monkeypatch.setenv("SEMANTIC_STORE_PATH", str(tmp_path / "semantic-store.json"))
    monkeypatch.setattr("services.api_service.main.decode_access_token", lambda token: {"sub": "admin", "role": "admin"})
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    entity = client.post(
        "/api/v1/semantic/entities",
        headers=headers,
        json={
            "entity_id": "site/demo/asset-1",
            "entity_type": "asset",
            "name": "Asset 1",
            "labels": ["asset"],
            "metadata": {"site_id": "demo-site"},
        },
    )
    lineage = client.post(
        "/api/v1/semantic/lineage",
        headers=headers,
        json={
            "lineage_id": "lineage-1",
            "kind": "ingested_event",
            "source_id": "source-1",
            "entity_id": "site/demo/asset-1",
            "site_id": "demo-site",
            "occurred_at": "2026-07-04T00:00:00Z",
            "metadata": {"source_protocol": "mqtt"},
        },
    )

    assert entity.status_code == 200
    assert lineage.status_code == 200
    assert client.get("/api/v1/semantic/graph/entities/site/demo/asset-1").status_code == 200
    assert client.get("/api/v1/semantic/lineage", params={"site_id": "demo-site"}).json()["lineage"]

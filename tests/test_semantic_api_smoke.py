from __future__ import annotations

from fastapi.testclient import TestClient


def test_semantic_routes_return_graph_and_core_catalog() -> None:
    from services.api_service.main import app

    client = TestClient(app)

    core = client.get("/api/v1/semantic/core")
    graph = client.get("/api/v1/semantic/graph")
    search = client.get("/api/v1/semantic/graph/search", params={"q": "pump temperature", "limit": 5})

    assert core.status_code == 200
    assert graph.status_code == 200
    assert search.status_code == 200
    core_json = core.json()
    graph_json = graph.json()
    search_json = search.json()
    assert "Entity" in core_json["platform_primitives"]
    assert graph_json["counts"]["entities"] > 0
    assert search_json["entities"]

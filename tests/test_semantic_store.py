from __future__ import annotations

from pathlib import Path

from services.common.semantic_core import OntologyPack, SemanticEntity, SemanticGraph
from services.common.semantic_store import DatabaseSemanticStoreBackend, SemanticLineageRecord, get_semantic_store


def test_semantic_store_persists_entities_and_lineage(tmp_path: Path, monkeypatch) -> None:
    store_path = tmp_path / "semantic-store.json"
    monkeypatch.setenv("SEMANTIC_STORE_PATH", str(store_path))

    store = get_semantic_store(store_path)
    store.upsert_ontology_pack(
        OntologyPack(
            pack_id="industry.semiconductor",
            name="Semiconductor Pack",
            layer="industry",
            version="1.0",
            concepts=("Wafer", "Lot"),
            notes=("test pack",),
        )
    )
    store.upsert_entity(
        SemanticEntity(
            entity_id="site/test-line/pump-01",
            entity_type="pump",
            name="Pump 01",
            labels=("asset", "pump"),
            metadata={"site_id": "demo-site"},
        )
    )
    store.record_lineage(
        SemanticLineageRecord(
            lineage_id="lineage-1",
            kind="ingested_event",
            source_id="source-1",
            entity_id="site/test-line/pump-01",
            site_id="demo-site",
            occurred_at="2026-07-04T00:00:00Z",
            metadata={"source_protocol": "mqtt"},
        )
    )

    reloaded = get_semantic_store(store_path)
    snapshot = reloaded.snapshot()
    assert snapshot["graph"]["entities"]
    assert snapshot["lineage"]
    assert any(pack["pack_id"] == "industry.semiconductor" for pack in snapshot["graph"]["ontology_packs"])
    assert snapshot["lineage"][0]["lineage_id"] == "lineage-1"


def test_database_semantic_store_uses_historian_helpers(monkeypatch) -> None:
    import services.historian.client as historian_client

    graph = SemanticGraph.default()
    graph.add_entity(
        SemanticEntity(
            entity_id="site/demo/asset-1",
            entity_type="asset",
            name="Asset 1",
            labels=("asset",),
            metadata={"site_id": "demo-site"},
        )
    )

    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(historian_client, "load_semantic_graph", lambda: graph.to_dict())
    monkeypatch.setattr(
        historian_client,
        "_semantic_upsert",
        lambda table, key, row, json_columns=None: calls.append((table, row[key])) or row,
    )
    monkeypatch.setattr(historian_client, "upsert_semantic_lineage", lambda row: row)
    monkeypatch.setattr(historian_client, "list_semantic_lineage", lambda site_id=None, limit=100: [{"lineage_id": "lineage-1"}])

    backend = DatabaseSemanticStoreBackend()
    snapshot = backend.list_ontology_packs()
    assert snapshot

    entity = backend.upsert_entity(
        SemanticEntity(
            entity_id="site/demo/asset-2",
            entity_type="asset",
            name="Asset 2",
            labels=("asset",),
            metadata={"site_id": "demo-site"},
        )
    )
    lineage = backend.record_lineage(
        SemanticLineageRecord(
            lineage_id="lineage-2",
            kind="ingested_event",
            source_id="source-2",
            site_id="demo-site",
            occurred_at="2026-07-04T00:00:00Z",
        )
    )

    assert entity["entity_id"] == "site/demo/asset-2"
    assert lineage["lineage_id"] == "lineage-2"
    assert ("semantic_entities", "site/demo/asset-2") in calls

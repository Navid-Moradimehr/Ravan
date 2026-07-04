from __future__ import annotations

from pathlib import Path

from services.common.semantic_core import OntologyPack, SemanticEntity
from services.common.semantic_store import SemanticLineageRecord, get_semantic_store


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

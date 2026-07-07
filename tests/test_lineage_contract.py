from __future__ import annotations

from fastapi.testclient import TestClient


def test_lineage_snapshot_exposes_openlineage_style_records(tmp_path, monkeypatch) -> None:
    import services.common.lineage_contract as lineage_contract
    from services.common.semantic_store import SemanticLineageRecord

    class FakeStore:
        def list_lineage(self, site_id=None, limit=100):
            return [
                SemanticLineageRecord(
                    lineage_id="lineage-1",
                    kind="ingested_event",
                    source_id="source-1",
                    target_id="target-1",
                    entity_id="entity-1",
                    site_id="demo-site",
                    dataset_id="dataset-1",
                    model_version="model-v1",
                    processing_version="proc-v1",
                    occurred_at="2026-07-04T00:00:00Z",
                    metadata={"source_protocol": "mqtt"},
                ).to_dict()
            ]

    monkeypatch.setattr(lineage_contract, "get_semantic_store", lambda: FakeStore())

    snapshot = lineage_contract.build_lineage_snapshot(site_id="demo-site", limit=10)

    assert snapshot["openlineage_compatible"] is True
    assert snapshot["total_records"] == 1
    assert snapshot["by_kind"]["ingested_event"] == 1
    assert snapshot["by_site"]["demo-site"] == 1
    assert snapshot["records"][0]["openlineage"]["job"]["name"] == "ingested_event"
    assert snapshot["records"][0]["openlineage"]["run"]["runId"] == "lineage-1"


def test_lineage_snapshot_api_route_returns_snapshot(monkeypatch) -> None:
    import services.common.lineage_contract as lineage_contract
    from services.api_service.main import app

    monkeypatch.setattr(
        lineage_contract,
        "build_lineage_snapshot",
        lambda site_id=None, limit=100: {"openlineage_compatible": True, "total_records": 0, "records": [], "by_kind": {}, "by_site": {}, "by_dataset": {}, "by_model_version": {}, "by_processing_version": {}, "generated_at": "2026-07-07T00:00:00Z"},
    )

    client = TestClient(app)
    response = client.get("/api/v1/lineage")

    assert response.status_code == 200
    body = response.json()
    assert body["openlineage_compatible"] is True


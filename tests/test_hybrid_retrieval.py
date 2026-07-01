from __future__ import annotations

from services.common import retrieval


def test_hybrid_search_prioritizes_alarm_like_match(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "disabled")

    monkeypatch.setattr(
        retrieval,
        "query_recent_events",
        lambda table, limit: [
            {
                "event_id": "e-1",
                "time": "2026-07-01T00:00:00Z",
                "asset_id": "compressor-1",
                "tag": "motor_vibration",
                "value": 98.2,
                "severity": "warning",
                "quality": "good",
                "fault_type": "overheat",
                "evaluation": {"status": "alarm"},
            }
        ],
    )
    monkeypatch.setattr(
        retrieval,
        "query_alarms",
        lambda limit: [
            {
                "time": "2026-07-01T00:05:00Z",
                "asset_id": "compressor-1",
                "tag": "motor_vibration",
                "severity": "critical",
                "message": "Motor overheating alarm",
            }
        ],
    )
    monkeypatch.setattr(retrieval, "list_scenarios", lambda: [])
    monkeypatch.setattr(
        retrieval.report_engine,
        "list_templates",
        lambda: [
            {
                "template_id": "r-1",
                "name": "Daily production report",
                "description": "Production summary template",
                "format": "pdf",
            }
        ],
    )
    monkeypatch.setattr(
        retrieval,
        "load_hierarchy",
        lambda asset_config: [{"id": "compressor-1", "name": "Compressor 1", "type": "machine", "path": "plant/line1/compressor-1"}],
    )
    monkeypatch.setattr(retrieval, "hierarchy_to_tree", lambda items: items)

    result = retrieval.search_retrieval_corpus(
        "motor overheating alarm",
        table="industrial_events",
        limit=5,
        max_results=3,
        use_embeddings=True,
    )

    assert result["mode"] == "hybrid"
    assert result["hits"]
    assert result["hits"][0]["doc_id"].startswith("alarm:")
    assert "signals" in result["hits"][0]
    assert result["hits"][0]["signals"]["token"] >= result["hits"][0]["signals"]["phrase"]


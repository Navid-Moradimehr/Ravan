from __future__ import annotations


def test_retrieval_search_ranks_matching_docs(monkeypatch):
    import services.common.retrieval as retrieval

    monkeypatch.setattr(
        retrieval,
        "query_recent_events",
        lambda table, limit: [
            {
                "event_id": "evt-1",
                "time": "2026-07-01T10:00:00Z",
                "asset_id": "Pump-01",
                "tag": "Temperature",
                "value": 81.2,
                "severity": "critical",
                "quality": "good",
                "fault_type": "overheat",
            },
            {
                "event_id": "evt-2",
                "time": "2026-07-01T10:01:00Z",
                "asset_id": "Pump-02",
                "tag": "Pressure",
                "value": 6.2,
                "severity": "warning",
                "quality": "good",
                "fault_type": "normal",
            },
        ],
    )
    monkeypatch.setattr(
        retrieval,
        "query_alarms",
        lambda limit: [{"time": "2026-07-01T10:02:00Z", "asset_id": "Pump-01", "tag": "Temperature", "severity": "critical", "message": "Alarm"}],
    )
    monkeypatch.setattr(retrieval, "load_hierarchy", lambda path: {"root": True})
    monkeypatch.setattr(retrieval, "hierarchy_to_tree", lambda hierarchy: [{"id": "Pump-01", "name": "Pump 01", "type": "asset", "path": "plant/line-1"}])
    monkeypatch.setattr(retrieval.report_engine, "list_templates", lambda: [{"template_id": "daily_alarms", "name": "Daily Alarms"}])
    monkeypatch.setattr(retrieval, "list_scenarios", lambda: [{"scenario_id": "normal", "name": "Normal Run"}])

    result = retrieval.search_retrieval_corpus("pump temperature alarm", limit=10, max_results=3)
    assert result["documents_indexed"] >= 4
    assert result["result_count"] >= 1
    assert result["hits"][0]["score"] >= result["hits"][-1]["score"]
    assert "pump" in result["hits"][0]["snippet"].lower() or "temperature" in result["hits"][0]["snippet"].lower()


def test_retrieval_catalog_lists_read_only_sources(monkeypatch):
    import services.common.retrieval as retrieval

    monkeypatch.setattr(retrieval, "load_hierarchy", lambda path: [{"id": "Pump-01"}])
    monkeypatch.setattr(retrieval, "hierarchy_to_tree", lambda hierarchy: hierarchy)

    catalog = retrieval.build_retrieval_catalog()
    assert any(source["name"] == "historian.events" for source in catalog["sources"])
    assert all(source["read_only"] for source in catalog["sources"])

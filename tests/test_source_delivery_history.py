from __future__ import annotations


def test_source_delivery_history_is_bounded_and_redacts_error(tmp_path, monkeypatch):
    from services.edge_ingest import delivery_history

    monkeypatch.setattr(delivery_history, "PATH", tmp_path / "delivery.json")
    monkeypatch.setattr(delivery_history, "MAX_RECORDS", 2)
    delivery_history.record_delivery(connection_id="c1", protocol="rest", site="plant-a", status="accepted", records=3)
    delivery_history.record_delivery(connection_id="c1", protocol="rest", site="plant-a", status="failed", error="x" * 700)
    delivery_history.record_delivery(connection_id="c2", protocol="http_push", site="plant-b", status="accepted", records=1)
    records = delivery_history.recent()
    assert len(records) == 2
    assert records[0]["connection_id"] == "c2"
    assert len(records[1]["error"]) == 500

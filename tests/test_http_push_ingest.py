from __future__ import annotations

import asyncio


def test_http_push_requires_enabled_registered_connection(tmp_path, monkeypatch):
    import services.api_service.routers.historian as module
    from services.common.connection_registry import ConnectionRegistry, SourceConnection

    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(SourceConnection("push-1", "Gateway", "http_push", "plant-a"))
    monkeypatch.setattr(module, "connection_registry", registry, raising=False)

    try:
        asyncio.run(module.push_connection_event("push-1", {"value": 1}))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("disabled HTTP push source accepted an event")


def test_http_push_reuses_canonical_ingress_and_deduplicates(tmp_path, monkeypatch):
    import services.api_service.routers.historian as module
    from services.common.connection_registry import ConnectionRegistry, SourceConnection

    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(SourceConnection("push-1", "Gateway", "http_push", "plant-a"))
    registry.set_enabled("push-1", True)
    monkeypatch.setattr(module, "connection_registry", registry, raising=False)
    import services.api_service.http_push_idempotency as idempotency
    import services.edge_ingest.delivery_history as delivery_history
    monkeypatch.setattr(delivery_history, "PATH", tmp_path / "source-delivery.json")
    claimed: set[str] = set()
    responses: dict[str, dict[str, object]] = {}
    def claim(key: str, event_id: str = ""):
        if key in claimed:
            return {**responses[key], "status": "duplicate"}
        claimed.add(key)
        return None
    monkeypatch.setattr(idempotency, "claim", claim)
    monkeypatch.setattr(idempotency, "complete", lambda key, response: responses.__setitem__(key, response))
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(module, "_do_ingest_event", lambda event: calls.append(event) or {"status": "ingested", "event_id": "evt-1"})

    first = asyncio.run(module.push_connection_event("push-1", {"event_id": "evt-1", "asset_id": "Pump-1", "tag": "Temperature", "value": 20}))
    second = asyncio.run(module.push_connection_event("push-1", {"event_id": "evt-1", "asset_id": "Pump-1", "tag": "Temperature", "value": 20}))

    assert first["status"] == "ingested"
    assert second["status"] == "duplicate"
    assert len(calls) == 1
    assert calls[0]["source_protocol"] == "http_push"
    assert calls[0]["site"] == "plant-a"

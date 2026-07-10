from __future__ import annotations

import asyncio


def test_modbus_preview_returns_declared_register_map(tmp_path, monkeypatch):
    import services.api_service.routers.connections as module
    from services.common.connection_registry import ConnectionRegistry, SourceConnection

    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(SourceConnection("modbus-1", "Meter", "modbus", "plant-a", "modbus://127.0.0.1:502", config={"registers": [{"address": 12, "tag": "Flow", "unit": "l/min", "scale": 0.1, "unit_id": 3}]}))
    monkeypatch.setattr(module, "connection_registry", registry)

    result = asyncio.run(module.preview_connection("modbus-1"))

    assert result["preview"] == "modbus"
    assert result["registers"][0]["address"] == 12

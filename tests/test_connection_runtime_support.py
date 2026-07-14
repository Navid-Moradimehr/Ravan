from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException


def test_enable_rejects_metadata_only_connection(tmp_path, monkeypatch):
    import services.api_service.routers.connections as module
    from services.common.connection_registry import ConnectionRegistry, SourceConnection

    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(
        SourceConnection(
            "conn-rest",
            "REST metadata",
            "rest",
            "plant-a",
            "https://example.test/api",
            config={"url": "https://example.test/api"},
        )
    )
    monkeypatch.setattr(module, "connection_registry", registry)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.enable_connection("conn-rest"))

    assert exc_info.value.status_code == 422
    assert "metadata-only" in str(exc_info.value.detail)


def test_retired_connections_cannot_be_enabled(tmp_path, monkeypatch):
    import services.api_service.routers.connections as module
    from services.common.connection_registry import ConnectionRegistry, SourceConnection

    registry = ConnectionRegistry(tmp_path / "connections.json")
    registry.put(
        SourceConnection(
            "conn-opcua",
            "Pump OPC UA",
            "opcua",
            "plant-a",
            "opc.tcp://example.test:4840",
        )
    )
    registry.retire("conn-opcua")
    monkeypatch.setattr(module, "connection_registry", registry)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.enable_connection("conn-opcua"))

    assert exc_info.value.status_code == 422
    assert "restored" in str(exc_info.value.detail)

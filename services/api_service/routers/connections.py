from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.common.connection_registry import ConnectionValidationError, SourceConnection, SourceMapping, connection_registry
from services.common.connection_diagnostics import run_connection_test

router = APIRouter(tags=["connections"])


class MappingRequest(BaseModel):
    source_field: str
    asset_id: str
    tag: str
    site_id: str = ""
    line: str = ""
    unit: str = ""
    scale: float = 1.0
    offset: float = 0.0
    quality_field: str = ""
    timestamp_field: str = ""
    value_kind: str = "measurement"


class ConnectionRequest(BaseModel):
    connection_id: str | None = None
    name: str
    source_protocol: str
    site_id: str
    endpoint: str = ""
    source_id: str = ""
    credential_ref: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    mappings: list[MappingRequest] = Field(default_factory=list)
    enabled: bool = False


def _to_connection(request: ConnectionRequest, connection_id: str | None = None) -> SourceConnection:
    import uuid

    return SourceConnection(
        connection_id=connection_id or request.connection_id or f"conn-{uuid.uuid4().hex[:12]}",
        name=request.name,
        source_protocol=request.source_protocol,
        site_id=request.site_id,
        endpoint=request.endpoint,
        source_id=request.source_id,
        credential_ref=request.credential_ref,
        config=request.config,
        mappings=[SourceMapping(**mapping.model_dump()) for mapping in request.mappings],
        enabled=request.enabled,
        state="enabled" if request.enabled else "configured",
    )


@router.get("/api/v1/connections")
async def list_connections(site_id: str | None = None, enabled: bool | None = None) -> dict[str, Any]:
    return {"connections": [item.to_dict() for item in connection_registry.list(site_id=site_id, enabled=enabled)]}


@router.post("/api/v1/connections")
async def create_connection(request: ConnectionRequest) -> dict[str, Any]:
    try:
        connection = connection_registry.put(_to_connection(request))
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return connection.to_dict()


@router.get("/api/v1/connections/{connection_id}")
async def get_connection(connection_id: str) -> dict[str, Any]:
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection.to_dict()


@router.put("/api/v1/connections/{connection_id}")
async def update_connection(connection_id: str, request: ConnectionRequest) -> dict[str, Any]:
    if connection_registry.get(connection_id) is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        connection = connection_registry.put(_to_connection(request, connection_id))
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return connection.to_dict()


@router.delete("/api/v1/connections/{connection_id}")
async def delete_connection(connection_id: str) -> dict[str, str]:
    if not connection_registry.delete(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "deleted", "connection_id": connection_id}


@router.post("/api/v1/connections/{connection_id}/enable")
async def enable_connection(connection_id: str) -> dict[str, Any]:
    try:
        return connection_registry.set_enabled(connection_id, True).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc


@router.post("/api/v1/connections/{connection_id}/disable")
async def disable_connection(connection_id: str) -> dict[str, Any]:
    try:
        return connection_registry.set_enabled(connection_id, False).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc


@router.post("/api/v1/connections/{connection_id}/validate")
async def validate_connection(connection_id: str) -> dict[str, Any]:
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    errors = connection.validate()
    return {"connection_id": connection_id, "valid": not errors, "errors": errors, "network_test": "not_run"}


@router.post("/api/v1/connections/{connection_id}/test")
async def test_connection_endpoint(connection_id: str) -> dict[str, Any]:
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return run_connection_test(connection)


@router.post("/api/v1/connections/{connection_id}/preview")
async def preview_connection(connection_id: str, node_id: str | None = None, max_tags: int = 100) -> dict[str, Any]:
    """Preview source metadata without enabling ingestion or publishing events."""
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if connection.source_protocol == "opcua":
        from services.edge_ingest.opcua_discovery import OPCUADiscoveryClient

        client = OPCUADiscoveryClient(connection.endpoint)
        connected = await asyncio.wait_for(client.connect(), timeout=5.0)
        if not connected:
            return {"connection_id": connection_id, "preview": "unavailable", "error": "OPC UA connection failed"}
        try:
            if node_id:
                tags = [await asyncio.wait_for(client.read_tag(node_id), timeout=5.0)]
            else:
                tags = (await asyncio.wait_for(client.browse_tags(), timeout=10.0))[:max(1, min(max_tags, 1000))]
            return {"connection_id": connection_id, "preview": "opcua", "endpoint": connection.endpoint, "tags": tags}
        finally:
            await client.disconnect()
    if connection.source_protocol in {"modbus", "modbus_rtu"}:
        return {"connection_id": connection_id, "preview": "modbus", "registers": connection.config.get("registers", []), "config": connection.config}
    if connection.source_protocol in {"mqtt", "sparkplug_b"}:
        return {"connection_id": connection_id, "preview": "mqtt", "topic": connection.config.get("topic", ""), "payload_mode": connection.config.get("payload_mode", "json")}
    return {"connection_id": connection_id, "preview": "configuration", "config": connection.config}

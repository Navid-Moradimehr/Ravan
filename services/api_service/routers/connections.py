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
    credential_refs: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    mappings: list[MappingRequest] = Field(default_factory=list)
    enabled: bool = False


class OPCUABrowseSelectionRequest(BaseModel):
    node_ids: list[str] = Field(..., min_length=1, max_length=500)


def _to_connection(
    request: ConnectionRequest,
    connection_id: str | None = None,
    *,
    existing: SourceConnection | None = None,
) -> SourceConnection:
    import uuid

    connection = SourceConnection(
        connection_id=connection_id or request.connection_id or f"conn-{uuid.uuid4().hex[:12]}",
        name=request.name,
        source_protocol=request.source_protocol,
        site_id=request.site_id,
        endpoint=request.endpoint,
        source_id=request.source_id,
        credential_ref=request.credential_ref,
        credential_refs=request.credential_refs,
        config=request.config,
        mappings=[SourceMapping(**mapping.model_dump()) for mapping in request.mappings],
        enabled=request.enabled,
        state="enabled" if request.enabled else "configured",
    )
    if existing is not None:
        connection.created_at = existing.created_at
        connection.updated_at = existing.updated_at
        connection.last_error = existing.last_error
        connection.last_success_at = existing.last_success_at
        connection.retired_at = existing.retired_at
        connection.retired_reason = existing.retired_reason
        if existing.state == "retired":
            connection.state = "retired"
            connection.enabled = False
        else:
            connection.state = existing.state
            connection.enabled = existing.enabled
    return connection


@router.get("/api/v1/connections")
async def list_connections(site_id: str | None = None, enabled: bool | None = None, include_retired: bool = True) -> dict[str, Any]:
    return {
        "connections": [
            item.to_dict()
            for item in connection_registry.list(site_id=site_id, enabled=enabled, include_retired=include_retired)
        ]
    }


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
    existing = connection_registry.get(connection_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        connection = connection_registry.put(_to_connection(request, connection_id, existing=existing))
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return connection.to_dict()


@router.delete("/api/v1/connections/{connection_id}")
async def delete_connection(connection_id: str) -> dict[str, str]:
    if not connection_registry.delete(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "retired", "connection_id": connection_id}


@router.post("/api/v1/connections/{connection_id}/retire")
async def retire_connection(connection_id: str) -> dict[str, Any]:
    try:
        connection = connection_registry.retire(connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    return connection.to_dict()


@router.post("/api/v1/connections/{connection_id}/restore")
async def restore_connection(connection_id: str) -> dict[str, Any]:
    try:
        connection = connection_registry.restore(connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    return connection.to_dict()


@router.post("/api/v1/connections/{connection_id}/enable")
async def enable_connection(connection_id: str) -> dict[str, Any]:
    try:
        connection = connection_registry.get(connection_id)
        if connection is None:
            raise HTTPException(status_code=404, detail="Connection not found")
        if connection.state == "retired":
            raise HTTPException(status_code=422, detail="retired connections must be restored before they can be enabled")
        if not connection.runtime_supported:
            raise HTTPException(
                status_code=422,
                detail=f"source_protocol {connection.source_protocol} is metadata-only and cannot be enabled by the edge runtime",
            )
        return connection_registry.set_enabled(connection_id, True).to_dict()
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc


@router.post("/api/v1/connections/{connection_id}/disable")
async def disable_connection(connection_id: str) -> dict[str, Any]:
    try:
        return connection_registry.set_enabled(connection_id, False).to_dict()
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc


@router.post("/api/v1/connections/{connection_id}/validate")
async def validate_connection(connection_id: str) -> dict[str, Any]:
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    draft_errors = connection.validate_draft()
    activation_errors = connection.activation_errors()
    return {
        "connection_id": connection_id,
        "valid": not draft_errors,
        "activation_ready": not activation_errors,
        "errors": draft_errors,
        "missing_fields": [error for error in activation_errors if error not in draft_errors],
        "warnings": [
            "Credentials are references only; the deployment must provide the referenced values."
            if connection.credential_refs else "No credentials configured; anonymous access must be accepted by the source."
        ],
        "network_test": "not_run",
        "runtime_supported": connection.runtime_supported,
        "runtime_note": connection.runtime_note,
        "capabilities": list(connection.capabilities),
    }


@router.post("/api/v1/connections/{connection_id}/opcua/browse-selection")
async def save_opcua_browse_selection(connection_id: str, request: OPCUABrowseSelectionRequest) -> dict[str, Any]:
    try:
        connection = connection_registry.save_opcua_browse_selection(connection_id, request.node_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"connection_id": connection_id, "node_ids": connection.config.get("nodes", []), "config_version": connection.config_version, "state": connection.state}


@router.post("/api/v1/connections/{connection_id}/test")
async def test_connection_endpoint(connection_id: str) -> dict[str, Any]:
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return run_connection_test(connection)


@router.post("/api/v1/connections/{connection_id}/preview")
async def preview_connection(connection_id: str, node_id: str | None = None, max_tags: int = 100, max_depth: int = 5) -> dict[str, Any]:
    """Preview source metadata without enabling ingestion or publishing events."""
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if connection.source_protocol == "opcua":
        from services.edge_ingest.opcua_discovery import OPCUADiscoveryClient

        client = OPCUADiscoveryClient(connection.endpoint, credential_refs=connection.credential_refs, security=connection.config.get("security", {}))
        connected = await asyncio.wait_for(client.connect(), timeout=5.0)
        if not connected:
            return {"connection_id": connection_id, "preview": "unavailable", "error": "OPC UA connection failed"}
        try:
            if node_id:
                tags = [await asyncio.wait_for(client.read_tag(node_id), timeout=5.0)]
            else:
                tags = (await asyncio.wait_for(client.browse_tags(max_depth=max_depth), timeout=10.0))[:max(1, min(max_tags, 1000))]
            return {"connection_id": connection_id, "preview": "opcua", "endpoint": connection.endpoint, "tags": tags}
        finally:
            await client.disconnect()
    if connection.source_protocol in {"modbus", "modbus_rtu"}:
        return {"connection_id": connection_id, "preview": "modbus", "registers": connection.config.get("registers", []), "config": connection.config, "activation_ready": connection.activation_ready}
    if connection.source_protocol in {"mqtt", "sparkplug_b"}:
        return {"connection_id": connection_id, "preview": "mqtt", "topic": connection.config.get("topic", ""), "payload_mode": connection.config.get("payload_mode", "json")}
    return {"connection_id": connection_id, "preview": "configuration", "config": connection.config, "activation_ready": connection.activation_ready}

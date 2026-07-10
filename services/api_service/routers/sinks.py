"""API for deployment-owned sink routing metadata."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.common.sink_routing import SinkRoute, sink_route_registry

router = APIRouter()


class SinkRouteRequest(BaseModel):
    name: str
    sink_type: str
    enabled: bool = True
    topic: str = ""
    credential_ref: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/v1/sinks")
async def list_sink_routes() -> dict[str, Any]:
    return {"routes": [route.to_dict() for route in sink_route_registry.list()]}


@router.post("/api/v1/sinks")
async def create_sink_route(request: SinkRouteRequest) -> dict[str, Any]:
    try:
        route = sink_route_registry.put(SinkRoute(route_id=f"sink-{uuid.uuid4().hex[:12]}", **request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "registered", "route": route.to_dict(), "restart_required": True}


@router.put("/api/v1/sinks/{route_id}")
async def update_sink_route(route_id: str, request: SinkRouteRequest) -> dict[str, Any]:
    if sink_route_registry.get(route_id) is None:
        raise HTTPException(status_code=404, detail="Sink route not found")
    try:
        route = sink_route_registry.put(SinkRoute(route_id=route_id, **request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "updated", "route": route.to_dict(), "restart_required": True}


@router.delete("/api/v1/sinks/{route_id}")
async def delete_sink_route(route_id: str) -> dict[str, str]:
    if not sink_route_registry.delete(route_id):
        raise HTTPException(status_code=404, detail="Sink route not found")
    return {"status": "deleted", "route_id": route_id, "restart_required": True}

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["external"])


class AssetCreateRequest(BaseModel):
    id: str
    name: str
    type: str
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TagCreateRequest(BaseModel):
    id: str
    name: str
    unit: str
    min: float
    max: float
    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    sampling_rate_hz: float = 1.0


@router.post("/api/v1/assets/external")
async def create_external_asset(req: AssetCreateRequest) -> dict[str, Any]:
    from services.assets.model import AssetNode, add_asset

    asset = AssetNode(
        id=req.id,
        name=req.name,
        type=req.type,
        parent_id=req.parent_id,
        metadata=req.metadata,
    )
    add_asset(asset)
    return {"status": "created", "asset": asset.to_dict()}


@router.get("/api/v1/assets/external/{asset_id}")
async def get_external_asset(asset_id: str) -> dict[str, Any]:
    from services.assets.model import get_asset

    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset.to_dict()


@router.put("/api/v1/assets/external/{asset_id}")
async def update_external_asset(asset_id: str, req: AssetCreateRequest) -> dict[str, Any]:
    from services.assets.model import update_asset

    asset = update_asset(asset_id, name=req.name, type=req.type, metadata=req.metadata)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "updated", "asset": asset.to_dict()}


@router.delete("/api/v1/assets/external/{asset_id}")
async def delete_external_asset(asset_id: str) -> dict[str, str]:
    from services.assets.model import delete_asset

    if delete_asset(asset_id):
        return {"status": "deleted", "asset_id": asset_id}
    raise HTTPException(status_code=404, detail="Asset not found")


@router.post("/api/v1/assets/external/{asset_id}/tags")
async def add_asset_tag(asset_id: str, req: TagCreateRequest) -> dict[str, Any]:
    from services.assets.model import add_tag_to_asset

    tag = add_tag_to_asset(
        asset_id=asset_id,
        tag_id=req.id,
        name=req.name,
        unit=req.unit,
        min_val=req.min,
        max_val=req.max,
        warning_low=req.warning_low,
        warning_high=req.warning_high,
        critical_low=req.critical_low,
        critical_high=req.critical_high,
        sampling_rate_hz=req.sampling_rate_hz,
    )
    if not tag:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "created", "tag": tag}


@router.get("/api/v1/events/external")
async def get_external_events(
    asset_id: str | None = None,
    tag: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    from services.historian.client import query_sql

    conditions = []
    params = []
    if asset_id:
        conditions.append("asset_id = %s")
        params.append(asset_id)
    if tag:
        conditions.append("tag = %s")
        params.append(tag)
    if start_time:
        conditions.append("time >= %s")
        params.append(start_time)
    if end_time:
        conditions.append("time <= %s")
        params.append(end_time)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM industrial_events WHERE {where_clause} ORDER BY time DESC LIMIT %s"
    params.append(limit)
    return query_sql(sql, tuple(params))


@router.post("/api/v1/events/external")
async def ingest_external_event(event: dict[str, Any]) -> dict[str, str]:
    from services.common.normalize import normalize_runtime_event
    from services.historian.client import insert_industrial_event

    normalized = normalize_runtime_event(event)
    insert_industrial_event(normalized)
    return {"status": "received", "event_id": normalized.get("event_id", "unknown")}

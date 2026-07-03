from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException


router = APIRouter(tags=["connectors"])


@router.get("/api/v1/connectors")
async def list_connectors_endpoint(category: str | None = None, protocol: str | None = None) -> list[dict[str, Any]]:
    from services.datasets.data_sources_catalog import list_connectors

    return list_connectors(category, protocol)


@router.get("/api/v1/connectors/{connector_id}")
async def get_connector_endpoint(connector_id: str) -> dict[str, Any]:
    from services.datasets.data_sources_catalog import get_connector

    connector = get_connector(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector.__dict__

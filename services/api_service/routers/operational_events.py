from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from services.common.operational_event import OperationalEvent, publish_operational_event

router = APIRouter(tags=["operational-events"])


@router.post("/api/v1/operational/events")
async def ingest_operational_event(event: OperationalEvent) -> dict[str, Any]:
    try:
        return publish_operational_event(event)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"operational event publish failed: {exc}") from exc

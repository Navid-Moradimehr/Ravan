from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services.common.lineage_contract import build_lineage_snapshot


router = APIRouter(tags=["lineage"])


@router.get("/api/v1/lineage")
async def lineage_snapshot(site_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    return build_lineage_snapshot(site_id=site_id, limit=limit)


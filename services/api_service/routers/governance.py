from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services.common.governance_plane import build_governance_snapshot


router = APIRouter(tags=["governance"])


@router.get("/api/v1/metadata/governance")
async def governance_snapshot() -> dict[str, Any]:
    return build_governance_snapshot()

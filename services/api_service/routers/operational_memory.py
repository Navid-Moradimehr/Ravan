from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services.common.operational_memory import build_operational_memory_snapshot


router = APIRouter(tags=["operational-memory"])


@router.get("/api/v1/metadata/operational")
async def operational_memory_snapshot() -> dict[str, Any]:
    return build_operational_memory_snapshot()


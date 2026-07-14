from __future__ import annotations

from fastapi import APIRouter

from services.common.update_check import check_for_update


router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/update-status")
async def update_status() -> dict:
    """Return release metadata without downloading or installing anything."""
    return check_for_update().to_dict()

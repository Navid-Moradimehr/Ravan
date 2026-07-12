from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from services.common.threshold_policy import list_threshold_policies, upsert_threshold_policy


class ThresholdPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    site_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    tag: str = Field(min_length=1)
    unit: str = ""
    mode: str = "outside_range"
    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    deadband: float = 0
    on_delay_seconds: float = 0
    off_delay_seconds: float = 0
    enabled: bool = True
    source: str = "user"


router = APIRouter(prefix="/api/v1/metadata", tags=["threshold-policies"])


@router.get("/threshold-policies")
async def get_threshold_policies(site_id: str | None = None) -> dict[str, Any]:
    return list_threshold_policies(site_id=site_id)


@router.put("/threshold-policies")
async def put_threshold_policy(request: ThresholdPolicyRequest) -> dict[str, Any]:
    try:
        return {"ok": True, "policy": upsert_threshold_policy(request.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

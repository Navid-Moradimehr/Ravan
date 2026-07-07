from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.site_observability import build_site_observability_snapshot


router = APIRouter(tags=["observability"])


@router.get("/api/v1/observability/site")
async def site_observability(site_profile: str | None = None) -> dict[str, Any]:
    return build_site_observability_snapshot(
        site_profile_path=Path(site_profile) if site_profile else None,
    )


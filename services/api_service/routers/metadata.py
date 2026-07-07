from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.metadata_plane import build_metadata_plane_snapshot


router = APIRouter(tags=["metadata"])


@router.get("/api/v1/metadata")
async def metadata_snapshot(site_profile: str | None = None, asset_config: str | None = None) -> dict[str, Any]:
    return build_metadata_plane_snapshot(
        site_profile_path=Path(site_profile) if site_profile else None,
        asset_config=Path(asset_config) if asset_config else Path("config/assets.yaml"),
    )


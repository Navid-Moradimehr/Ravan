from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.asset_registry import build_asset_registry_snapshot
from services.common.asset_tag_catalog import list_asset_tags


router = APIRouter(tags=["asset-registry"])


@router.get("/api/v1/metadata/asset-tags")
async def asset_tag_catalog(
    asset_config: str | None = None,
    site_id: str | None = None,
    include_observed: bool = True,
    active_only: bool = True,
) -> dict[str, Any]:
    return list_asset_tags(
        asset_config=Path(asset_config) if asset_config else Path("config/assets.yaml"),
        site_id=site_id,
        include_observed=include_observed,
        active_only=active_only,
    )


@router.get("/api/v1/metadata/assets")
async def asset_registry_snapshot(
    asset_config: str | None = None,
    site_id: str | None = None,
) -> dict[str, Any]:
    return build_asset_registry_snapshot(
        asset_config=Path(asset_config) if asset_config else Path("config/assets.yaml"),
        site_id=site_id,
    )

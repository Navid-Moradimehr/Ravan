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


@router.get("/api/v1/metadata/federation")
async def federation_metadata(manifest_path: str = "config/project-manifest.yaml") -> dict[str, Any]:
    """Expose federation intent without exposing broker credentials or secrets."""
    from services.common.project_manifest import load_project_manifest, validate_project_manifest

    manifest = load_project_manifest(Path(manifest_path))
    errors = validate_project_manifest(manifest)
    return {
        "organization_id": manifest.organization_id or manifest.project_id,
        "project_id": manifest.project_id,
        "sites": [site.site_id for site in manifest.sites],
        "federation": manifest.federation.to_dict(),
        "lakehouse": manifest.lakehouse.to_dict(),
        "quality": manifest.quality.to_dict(),
        "valid": not errors,
        "validation_errors": errors,
    }

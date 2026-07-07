from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.event_catalog import build_event_catalog_snapshot


router = APIRouter(tags=["event-catalog"])


@router.get("/api/v1/metadata/events")
async def event_catalog_snapshot(project_manifest: str | None = None) -> dict[str, Any]:
    return build_event_catalog_snapshot(
        project_manifest_path=Path(project_manifest) if project_manifest else Path("config/project-manifest.yaml"),
    )

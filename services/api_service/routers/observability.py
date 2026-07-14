from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from services.common.site_observability import build_site_observability_snapshot


router = APIRouter(tags=["observability"])


@router.get("/api/v1/observability/site")
async def site_observability(site_profile: str | None = None) -> dict[str, Any]:
    return build_site_observability_snapshot(
        site_profile_path=Path(site_profile) if site_profile else None,
    )


@router.get("/api/v1/observability/source-health")
async def source_health(limit: int = 100) -> dict[str, Any]:
    try:
        from services.edge_ingest.source_health import history, snapshot

        return {"current": snapshot(), "history": history(limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"source health unavailable: {exc}") from exc


@router.get("/api/v1/observability/federation")
async def federation_observability() -> dict[str, Any]:
    from services.federation.health import federation_health

    return federation_health()

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


@router.get("/api/v1/observability/slo")
async def slo_observability(site_profile: str | None = None) -> dict[str, Any]:
    snapshot = build_site_observability_snapshot(
        site_profile_path=Path(site_profile) if site_profile else None,
    )
    return {
        "generated_at": snapshot["generated_at"],
        "deployment_mode": snapshot["deployment_mode"],
        "targets": snapshot["slo_targets"],
        "evaluation": snapshot["slo_evaluation"],
    }


@router.get("/api/v1/observability/source-health")
async def source_health(limit: int = 100, expected_interval_seconds: float = 10.0) -> dict[str, Any]:
    try:
        from services.common.runtime_lifecycle import enrich_source_health
        from services.edge_ingest.source_health import history, snapshot

        interval = max(expected_interval_seconds, 0.1)
        current = snapshot(expected_interval_seconds=interval)
        records = history(limit)
        # In Compose, edge-ingest and api-service are separate processes. The
        # API cannot see the edge module's in-memory map, so use the shared
        # bounded transition history to expose the latest known state.
        known = {str(item.get("connection_id")): item for item in current}
        for record in records:
            connection_id = str(record.get("connection_id", ""))
            if connection_id and connection_id not in known:
                known[connection_id] = enrich_source_health(record, expected_interval_seconds=interval)
        return {"current": list(known.values()), "history": records}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"source health unavailable: {exc}") from exc


@router.get("/api/v1/observability/source-delivery")
async def source_delivery(limit: int = 100) -> dict[str, Any]:
    try:
        from services.edge_ingest.delivery_history import recent
        return {"history": recent(limit)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"source delivery history unavailable: {exc}") from exc


@router.get("/api/v1/observability/federation")
async def federation_observability() -> dict[str, Any]:
    from services.federation.health import federation_health

    return federation_health()

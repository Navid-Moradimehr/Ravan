from __future__ import annotations

from typing import Any

from fastapi import APIRouter


router = APIRouter(tags=["pipelines"])


@router.get("/api/v1/pipelines")
async def list_pipelines() -> list[dict[str, Any]]:
    from services.processor.pipeline_designer import pipeline_registry

    return pipeline_registry.list_all()


@router.post("/api/v1/pipelines")
async def create_pipeline(req: dict[str, Any]) -> dict[str, str]:
    from services.processor.pipeline_designer import pipeline_registry

    topology = pipeline_registry.create(req.get("name", "untitled"), req.get("description", ""))
    return {"status": "created", "topology_id": topology.topology_id}


@router.delete("/api/v1/pipelines/{topology_id}")
async def delete_pipeline(topology_id: str) -> dict[str, str]:
    from services.processor.pipeline_designer import pipeline_registry

    pipeline_registry.delete(topology_id)
    return {"status": "deleted"}

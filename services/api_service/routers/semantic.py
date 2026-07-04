from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException

from services.common.semantic_core import build_semantic_core_catalog, load_semantic_graph_from_assets


router = APIRouter(tags=["semantic"])
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ASSET_HIERARCHY = REPO_ROOT / "config" / "assets.yaml"


def _semantic_graph():
    return load_semantic_graph_from_assets(DEFAULT_ASSET_HIERARCHY)


@router.get("/api/v1/semantic/core")
async def get_semantic_core() -> dict[str, Any]:
    return build_semantic_core_catalog()


@router.get("/api/v1/semantic/graph")
async def get_semantic_graph() -> dict[str, Any]:
    return _semantic_graph().to_dict()


@router.get("/api/v1/semantic/graph/search")
async def search_semantic_graph(q: str, limit: int = 10) -> dict[str, Any]:
    return _semantic_graph().graph_search(q, limit=limit)


@router.get("/api/v1/semantic/graph/entities/{entity_id}")
async def get_semantic_entity(entity_id: str) -> dict[str, Any]:
    graph = _semantic_graph()
    entity = graph.entities.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity.to_dict()


@router.get("/api/v1/semantic/graph/relationships/{relationship_id}")
async def get_semantic_relationship(relationship_id: str) -> dict[str, Any]:
    graph = _semantic_graph()
    relationship = graph.relationships.get(relationship_id)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return relationship.to_dict()

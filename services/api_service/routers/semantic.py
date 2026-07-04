from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.semantic_core import build_semantic_core_catalog, load_semantic_graph_from_assets


router = APIRouter(tags=["semantic"])
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ASSET_HIERARCHY = REPO_ROOT / "config" / "assets.yaml"


@router.get("/api/v1/semantic/core")
async def get_semantic_core() -> dict[str, Any]:
    return build_semantic_core_catalog()


@router.get("/api/v1/semantic/graph")
async def get_semantic_graph() -> dict[str, Any]:
    return load_semantic_graph_from_assets(DEFAULT_ASSET_HIERARCHY).to_dict()

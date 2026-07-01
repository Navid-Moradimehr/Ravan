from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.retrieval import build_retrieval_catalog, search_retrieval_corpus


router = APIRouter(tags=["retrieval"])


@router.get("/api/v1/retrieval/catalog")
async def retrieval_catalog(site_profile: str | None = None) -> dict[str, Any]:
    asset_config = Path("config/assets.yaml")
    return build_retrieval_catalog(asset_config=asset_config)


@router.get("/api/v1/retrieval/search")
async def retrieval_search(
    q: str,
    table: str = "industrial_events",
    limit: int = 25,
    max_results: int = 5,
) -> dict[str, Any]:
    return search_retrieval_corpus(query=q, table=table, limit=limit, max_results=max_results)


from __future__ import annotations

from typing import Any

from fastapi import APIRouter


router = APIRouter(tags=["preview"])


@router.get("/api/v1/preview/topics")
async def preview_topics() -> list[str]:
    from services.common.data_preview import list_topics

    return list_topics()


@router.get("/api/v1/preview/topics/{topic}")
async def preview_topic(topic: str, limit: int = 10) -> list[dict[str, Any]]:
    from services.common.data_preview import peek_topic

    return peek_topic(topic, limit=limit)


@router.post("/api/v1/preview/topics/{topic}/peek")
async def peek_topic_endpoint(topic: str, req: dict[str, Any]) -> list[dict[str, Any]]:
    from services.common.data_preview import peek_topic

    return peek_topic(topic, limit=req.get("limit", 10))

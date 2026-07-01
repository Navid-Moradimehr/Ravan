from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from services.common.agent_tools import build_context_package, tool_registry
from services.common.modeling import ModelRegistry
from services.common.prompt_registry import prompt_registry


router = APIRouter(tags=["modeling"])


@router.get("/api/v1/modeling/models")
async def list_models() -> dict[str, Any]:
    return ModelRegistry.from_env().export()


@router.get("/api/v1/modeling/tools")
async def list_tools() -> list[dict[str, Any]]:
    return tool_registry.list_tools()


@router.get("/api/v1/modeling/prompts")
async def list_prompts() -> list[dict[str, Any]]:
    return prompt_registry.list_templates()


@router.get("/api/v1/modeling/context")
async def get_context(
    asset_id: str | None = None,
    tag: str | None = None,
    table: str = "industrial_events",
    limit: int = 25,
    hours: int = 6,
    site_profile: str | None = None,
) -> dict[str, Any]:
    return build_context_package(
        asset_id=asset_id,
        tag=tag,
        table=table,
        limit=limit,
        hours=hours,
        site_profile_path=Path(site_profile) if site_profile else None,
    )


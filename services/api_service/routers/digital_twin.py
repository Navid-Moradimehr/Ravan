from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException


router = APIRouter(tags=["digital-twin"])


@router.get("/api/v1/digital-twin/scenes/{scene_id}")
async def get_digital_twin_scene(scene_id: str) -> dict[str, Any]:
    from services.assets.digital_twin import demo_scene

    return demo_scene.to_dict()


@router.post("/api/v1/digital-twin/scenes/{scene_id}/entities/{entity_id}/values")
async def update_twin_value(scene_id: str, entity_id: str, req: dict[str, Any]) -> dict[str, str]:
    from services.assets.digital_twin import demo_scene

    ok = demo_scene.update_value(entity_id, req.get("tag", ""), float(req.get("value", 0)))
    if not ok:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"status": "updated"}

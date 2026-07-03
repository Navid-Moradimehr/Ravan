from __future__ import annotations

from typing import Any

from fastapi import APIRouter


router = APIRouter(tags=["schemas"])


@router.get("/api/v1/schemas")
async def list_schemas() -> list[dict[str, Any]]:
    from services.common.schema_registry import schema_registry

    return schema_registry.list_schemas()


@router.post("/api/v1/schemas/{schema_id}/validate")
async def validate_schema(schema_id: str, req: dict[str, Any]) -> dict[str, Any]:
    from services.common.schema_registry import schema_registry

    return schema_registry.validate(schema_id, req.get("data", {}), req.get("version"))


@router.post("/api/v1/schemas")
async def register_schema(req: dict[str, Any]) -> dict[str, str]:
    from services.common.schema_registry import schema_registry

    schema_version = schema_registry.register(req.get("schema_id", "custom"), req.get("fields", []))
    return {"status": "registered", "schema_id": schema_version.schema_id, "version": str(schema_version.version)}

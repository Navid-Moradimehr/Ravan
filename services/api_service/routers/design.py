from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["design"])


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


@router.get("/api/v1/connectors")
async def list_connectors_endpoint(category: str | None = None, protocol: str | None = None) -> list[dict[str, Any]]:
    from services.datasets.data_sources_catalog import list_connectors

    return list_connectors(category, protocol)


@router.get("/api/v1/connectors/{connector_id}")
async def get_connector_endpoint(connector_id: str) -> dict[str, Any]:
    from services.datasets.data_sources_catalog import get_connector

    connector = get_connector(connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return connector.__dict__


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


@router.get("/api/v1/oee/shifts")
async def list_shifts(date: str | None = None) -> list[dict[str, Any]]:
    from services.analytics.oee_engine import oee_engine

    dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    return [shift.__dict__ for shift in oee_engine.generate_shifts(dt)]


@router.post("/api/v1/oee/calculate")
async def calculate_oee(req: dict[str, Any]) -> dict[str, Any]:
    from services.analytics.oee_engine import ShiftPeriod, oee_engine

    shift = ShiftPeriod(
        shift_id=req.get("shift_id", "unknown"),
        start=datetime.now(),
        end=datetime.now(),
        planned_production_time_minutes=req.get("planned_minutes", 480.0),
    )
    result = oee_engine.calculate(
        shift,
        runtime_minutes=req.get("runtime_minutes", 0.0),
        total_count=req.get("total_count", 0),
        good_count=req.get("good_count", 0),
    )
    return result.to_dict()

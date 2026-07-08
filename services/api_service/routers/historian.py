from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.api_service.runtime import _do_ingest_event, build_asset_hierarchy, list_scenarios
from services.api_service.replay_state import get_replay_status, start_replay, stop_replay
from services.historian.client import (
    get_storage_stats,
    insert_dead_letter,
    insert_ai_enriched,
    insert_industrial_event,
    insert_processed_event,
    query_alarms,
    query_tables,
    query_recent_events,
    query_sql_readonly,
    query_trend,
    setup_retention_policies,
    manual_compress_chunk,
)

router = APIRouter(tags=["historian"])


class SqlQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=2000)
    params: list[Any] = Field(default_factory=list)


@router.get("/api/v1/historian/tables")
async def get_tables() -> list[str]:
    try:
        return query_tables()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/v1/historian/query")
async def post_query(req: SqlQueryRequest) -> list[dict[str, Any]]:
    try:
        return query_sql_readonly(req.sql, tuple(req.params))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/v1/historian/alarms")
async def get_alarms(limit: int = 50) -> list[dict[str, Any]]:
    try:
        return query_alarms(limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/v1/historian/trend")
async def get_trend(asset_id: str, tag: str, hours: int = 1) -> list[dict[str, Any]]:
    try:
        return query_trend(asset_id, tag, hours)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/v1/historian/events")
async def get_events(table: str = "industrial_events", limit: int = 100) -> list[dict[str, Any]]:
    try:
        return query_recent_events(table, limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/v1/assets")
async def get_assets() -> list[dict[str, Any]]:
    return build_asset_hierarchy()


@router.get("/api/v1/scenarios")
async def get_scenarios() -> list[dict[str, Any]]:
    return list_scenarios()


@router.get("/api/v1/historian/replay")
async def get_replay_state() -> dict[str, Any]:
    return get_replay_status()


@router.post("/api/v1/historian/replay")
async def start_replay_job(req: dict[str, Any]) -> dict[str, Any]:
    dataset = str(req.get("dataset", "mock"))
    scenario = str(req.get("scenario", "normal"))
    try:
        state = start_replay(dataset, scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "replay": state}


@router.delete("/api/v1/historian/replay")
async def stop_replay_job() -> dict[str, Any]:
    return {"ok": True, "replay": stop_replay()}


@router.post("/api/v1/events/ingest")
async def ingest_event(event: dict[str, Any]) -> dict[str, str]:
    return _do_ingest_event(event)


@router.post("/api/v1/events/ingest/batch")
async def ingest_batch(req: dict[str, Any]) -> dict[str, Any]:
    table = req.get("table", "industrial_events")
    records = req.get("records", [])
    if not records:
        return {"status": "ok", "inserted": 0, "table": table}

    inserters = {
        "industrial_events": insert_industrial_event,
        "processed_events": insert_processed_event,
        "ai_enriched": insert_ai_enriched,
        "dead_letter_events": insert_dead_letter,
    }
    inserter = inserters.get(table)
    if inserter is None:
        raise HTTPException(status_code=400, detail=f"Unknown table: {table}")

    inserted = 0
    for record in records:
        try:
            inserter(record)
            inserted += 1
        except Exception:
            pass
    return {"status": "ok", "inserted": inserted, "table": table}


@router.post("/api/v1/historian/retention/setup")
async def setup_retention() -> dict[str, str]:
    try:
        setup_retention_policies()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/historian/storage")
async def storage_stats() -> dict[str, Any]:
    try:
        return get_storage_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/historian/dead-letters")
async def dead_letters(limit: int = 100) -> list[dict[str, Any]]:
    try:
        return query_recent_events("dead_letter_events", limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/historian/compress")
async def compress_historian(table: str, older_than_days: int = 7) -> dict[str, Any]:
    try:
        return manual_compress_chunk(table, older_than_days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

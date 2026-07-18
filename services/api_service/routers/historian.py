from __future__ import annotations

from typing import Any
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from services.api_service.runtime import _do_ingest_event, build_asset_hierarchy, list_scenarios
from services.api_service.replay_state import get_replay_status, start_replay, stop_replay
from services.historian.client import (
    get_storage_stats,
    insert_dead_letter,
    insert_ai_enriched,
    insert_industrial_event,
    insert_processed_event,
    cancel_historian_query,
    HistorianQueryCancelledError,
    HistorianQueryTimeoutError,
    query_alarms,
    query_tables,
    query_recent_events,
    query_sql_readonly,
    query_trend,
    setup_retention_policies,
    manual_compress_chunk,
)
from services.common.connection_registry import connection_registry
from services.api_service.http_push_idempotency import IdempotencyUnavailable

router = APIRouter(tags=["historian"])


class SqlQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=2000)
    params: list[Any] = Field(default_factory=list)
    query_id: str | None = Field(default=None, min_length=6, max_length=128)
    timeout_ms: int | None = Field(default=None, ge=1, le=600000)


@router.get("/api/v1/historian/tables")
async def get_tables() -> list[str]:
    try:
        return query_tables()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/api/v1/historian/query")
def post_query(req: SqlQueryRequest) -> list[dict[str, Any]]:
    try:
        return query_sql_readonly(req.sql, tuple(req.params), query_id=req.query_id, timeout_ms=req.timeout_ms)
    except HistorianQueryTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc))
    except HistorianQueryCancelledError as exc:
        raise HTTPException(status_code=499, detail=str(exc))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/v1/historian/query/{query_id}")
def delete_query(query_id: str) -> dict[str, Any]:
    try:
        return cancel_historian_query(query_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/historian/alarms")
async def get_alarms(limit: int = 50) -> list[dict[str, Any]]:
    try:
        return query_alarms(limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/api/v1/historian/trend")
async def get_trend(
    asset_id: str,
    tag: str,
    hours: int = 1,
    site_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    max_points: int = 2000,
    aggregation: str = "auto",
) -> list[dict[str, Any]]:
    try:
        return query_trend(asset_id, tag, hours, site_id=site_id, start=start, end=end, max_points=max_points, aggregation=aggregation)
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


@router.post("/api/v1/connections/{connection_id}/events")
async def push_connection_event(connection_id: str, event: dict[str, Any], idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, str]:
    """Receive a JSON event from an enabled HTTP Push source.

    Authentication remains an operator/deployment boundary. The route still
    requires a registered, enabled connection so arbitrary callers cannot
    create an untracked source definition by posting to the generic endpoint.
    """
    connection = connection_registry.get(connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    if connection.source_protocol != "http_push":
        raise HTTPException(status_code=422, detail="connection is not configured for http_push")
    if not connection.enabled:
        raise HTTPException(status_code=409, detail="connection must be enabled before it accepts events")
    key = idempotency_key or str(event.get("event_id", ""))
    durable_key = f"{connection_id}:{key}" if key else ""
    if durable_key:
        try:
            from services.api_service.http_push_idempotency import claim
            duplicate = claim(durable_key, str(event.get("event_id", "")))
        except IdempotencyUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if duplicate:
            return duplicate
    payload = {
        **event,
        "source_protocol": "http_push",
        "source_connection_id": connection_id,
        "site": event.get("site") or connection.site_id,
        "source_id": event.get("source_id") or connection.source_id or connection_id,
    }
    result = _do_ingest_event(payload)
    if result.get("status") == "publish_failed":
        if durable_key:
            try:
                from services.api_service.http_push_idempotency import release
                release(durable_key)
            except IdempotencyUnavailable:
                pass
        raise HTTPException(status_code=503, detail=result)
    result = {**result, "connection_id": connection_id}
    if durable_key:
        try:
            from services.api_service.http_push_idempotency import complete
            complete(durable_key, result)
        except IdempotencyUnavailable as exc:
            from services.api_service.http_push_idempotency import release
            try:
                release(durable_key)
            except IdempotencyUnavailable:
                pass
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        from services.edge_ingest.delivery_history import record_delivery
        record_delivery(connection_id=connection_id, protocol="http_push", site=connection.site_id, status="accepted", records=1)
    except Exception:
        pass
    return result


@router.post("/api/v1/connections/{connection_id}/events/batch")
async def push_connection_events(connection_id: str, body: list[dict[str, Any]], idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, Any]:
    if len(body) > 1000:
        raise HTTPException(status_code=413, detail="batch contains more than 1000 events")
    results = [await push_connection_event(connection_id, event, idempotency_key=f"{idempotency_key}:{index}" if idempotency_key else None) for index, event in enumerate(body)]
    return {"status": "accepted", "connection_id": connection_id, "accepted": sum(item.get("status") in {"ingested", "duplicate"} for item in results), "results": results}


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

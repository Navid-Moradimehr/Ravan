from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from historian.client import (
    query_sql,
    query_tables,
    query_alarms,
    query_trend,
    query_historian_events,
)
from assets.model import build_asset_hierarchy
from scenarios.engine import list_scenarios

API_PORT = int(os.getenv("API_SERVICE_PORT", "8020"))
TIMESCALE_API_BASE = os.getenv("TIMESCALE_API_BASE", "http://localhost:8010")


class SqlQueryRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=2000)
    params: list[Any] = Field(default_factory=list)


class WebhookConfig(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["alarm", "anomaly"])
    headers: dict[str, str] = Field(default_factory=dict)


class NotificationConfig(BaseModel):
    email: str | None = None
    webhook_url: str | None = None
    slack_webhook: str | None = None
    teams_webhook: str | None = None
    events: list[str] = Field(default_factory=lambda: ["alarm", "anomaly"])




# Use orjson for faster JSON responses if available
def _json_response(data):
    try:
        import orjson
        return ORJSONResponse(content=data)
    except ImportError:
        from fastapi.responses import JSONResponse
        return JSONResponse(content=data)
webhook_registry: dict[str, WebhookConfig] = {}
notification_registry: dict[str, NotificationConfig] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="Local Stream Engine API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/v1/historian/tables")
async def get_tables() -> list[str]:
    try:
        return query_tables()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/v1/historian/query")
async def post_query(req: SqlQueryRequest) -> list[dict[str, Any]]:
    try:
        return query_sql(req.sql, tuple(req.params))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/historian/alarms")
async def get_alarms(limit: int = 50) -> list[dict[str, Any]]:
    try:
        return query_alarms(limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/historian/trend")
async def get_trend(asset_id: str, tag: str, hours: int = 1) -> list[dict[str, Any]]:
    try:
        return query_trend(asset_id, tag, hours)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/historian/events")
async def get_events(table: str = "industrial_events", limit: int = 100) -> list[dict[str, Any]]:
    try:
        return query_historian_events(table, limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/assets")
async def get_assets() -> list[dict[str, Any]]:
    return build_asset_hierarchy()


@app.get("/api/v1/scenarios")
async def get_scenarios() -> list[dict[str, Any]]:
    return list_scenarios()


@app.post("/api/v1/webhooks")
async def register_webhook(config: WebhookConfig) -> dict[str, str]:
    import uuid
    hook_id = str(uuid.uuid4())[:8]
    webhook_registry[hook_id] = config
    return {"id": hook_id, "status": "registered"}


@app.get("/api/v1/webhooks")
async def list_webhooks() -> dict[str, Any]:
    return {"webhooks": {k: v.model_dump() for k, v in webhook_registry.items()}}


@app.delete("/api/v1/webhooks/{hook_id}")
async def delete_webhook(hook_id: str) -> dict[str, str]:
    if hook_id not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    del webhook_registry[hook_id]
    return {"status": "deleted"}


@app.post("/api/v1/notifications")
async def register_notification(config: NotificationConfig) -> dict[str, str]:
    import uuid
    notif_id = str(uuid.uuid4())[:8]
    notification_registry[notif_id] = config
    return {"id": notif_id, "status": "registered"}


@app.get("/api/v1/notifications")
async def list_notifications() -> dict[str, Any]:
    return {"notifications": {k: v.model_dump() for k, v in notification_registry.items()}}


@app.post("/api/v1/webhooks/test/{hook_id}")
async def test_webhook(hook_id: str) -> dict[str, str]:
    if hook_id not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    config = webhook_registry[hook_id]
    payload = {
        "event": "test",
        "message": "Webhook test from Local Stream Engine",
        "timestamp": "2024-01-01T00:00:00Z",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(config.url, json=payload, headers=config.headers, timeout=10.0)
            return {"status": "sent", "http_status": resp.status_code}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


@app.post("/api/v1/events/ingest")
async def ingest_event(event: dict[str, Any]) -> dict[str, str]:
    # Placeholder for external event ingestion
    return {"status": "received", "event_id": event.get("event_id", "unknown")}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

from rbac import Role, Permission, User, AuditLog, audit_log, create_user, get_user, authenticate_user, require_permission

class CreateUserRequest(BaseModel):
    user_id: str
    username: str
    role: str
    email: str | None = None

class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/api/v1/users")
async def create_user_endpoint(req: CreateUserRequest) -> dict[str, Any]:
    role = Role(req.role)
    user = create_user(req.user_id, req.username, role, req.email)
    return user.to_dict()

@app.get("/api/v1/users/{user_id}")
async def get_user_endpoint(user_id: str) -> dict[str, Any]:
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()

@app.post("/api/v1/auth/login")
async def login(req: AuthRequest) -> dict[str, Any]:
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    audit_log.log(user.user_id, "login", "auth")
    return {"token": f"mock-{user.user_id}", "user": user.to_dict()}

@app.get("/api/v1/audit-logs")
async def get_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    return audit_log.get_logs(limit)

from __future__ import annotations

import os
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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
WS_HEARTBEAT_INTERVAL = 15.0  # seconds


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


# WebSocket connection managers
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        dead = []
        async with self._lock:
            connections = list(self.active_connections)
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        if dead:
            async with self._lock:
                for d in dead:
                    if d in self.active_connections:
                        self.active_connections.remove(d)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]):
        try:
            await websocket.send_json(message)
        except Exception:
            await self.disconnect(websocket)


alarm_manager = ConnectionManager()
event_manager = ConnectionManager()
telemetry_manager = ConnectionManager()


# Background broadcaster: polls historian and pushes to WebSocket clients
async def _alarm_broadcaster():
    """Poll alarms periodically and broadcast only when data changes."""
    last_data: list[dict[str, Any]] = []
    while True:
        try:
            data = query_alarms(50)
            if data != last_data:
                last_data = data
                await alarm_manager.broadcast({"type": "update", "alarms": data})
        except Exception:
            pass
        await asyncio.sleep(2.0)


async def _event_broadcaster():
    """Poll events periodically and broadcast only when data changes."""
    last_data: dict[str, list[dict[str, Any]]] = {}
    tables = ["industrial_events", "processed_events", "ai_enriched"]
    while True:
        for table in tables:
            try:
                data = query_historian_events(table, 100)
                if data != last_data.get(table):
                    last_data[table] = data
                    await event_manager.broadcast({"type": "update", "table": table, "events": data})
            except Exception:
                pass
        await asyncio.sleep(2.0)


async def _telemetry_broadcaster():
    """Broadcast telemetry snapshot to all connected clients."""
    from ai_gateway.main import _build_telemetry
    while True:
        try:
            payload = await _build_telemetry()
            await telemetry_manager.broadcast({"type": "update", "telemetry": payload})
        except Exception:
            pass
        await asyncio.sleep(5.0)


async def _heartbeat_task():
    """Send periodic heartbeat to all WebSocket connections."""
    while True:
        await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
        await alarm_manager.broadcast({"type": "heartbeat"})
        await event_manager.broadcast({"type": "heartbeat"})
        await telemetry_manager.broadcast({"type": "heartbeat"})


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
    tasks = [
        asyncio.create_task(_alarm_broadcaster()),
        asyncio.create_task(_event_broadcaster()),
        asyncio.create_task(_telemetry_broadcaster()),
        asyncio.create_task(_heartbeat_task()),
    ]
    yield
    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Local Stream Engine API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket endpoints
@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket):
    await alarm_manager.connect(websocket)
    try:
        # Send initial data
        data = query_alarms(50)
        await websocket.send_json({"type": "init", "alarms": data})
        while True:
            # Wait for client messages (ping/ack/subscribe)
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif parsed.get("action") == "subscribe":
                    # Re-send current data on explicit subscribe
                    data = query_alarms(50)
                    await websocket.send_json({"type": "init", "alarms": data})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await alarm_manager.disconnect(websocket)


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await event_manager.connect(websocket)
    try:
        # Send initial data for all tables
        for table in ["industrial_events", "processed_events", "ai_enriched"]:
            data = query_historian_events(table, 100)
            await websocket.send_json({"type": "init", "table": table, "events": data})
        while True:
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif parsed.get("action") == "subscribe":
                    table = parsed.get("table", "industrial_events")
                    data = query_historian_events(table, 100)
                    await websocket.send_json({"type": "init", "table": table, "events": data})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await event_manager.disconnect(websocket)


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await telemetry_manager.connect(websocket)
    try:
        from ai_gateway.main import _build_telemetry
        payload = await _build_telemetry()
        await websocket.send_json({"type": "init", "telemetry": payload})
        while True:
            msg = await websocket.receive_text()
            try:
                parsed = json.loads(msg)
                if parsed.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await telemetry_manager.disconnect(websocket)


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


# Data retention and storage management endpoints
@app.post("/api/v1/historian/retention/setup")
async def setup_retention() -> dict[str, str]:
    from historian.client import setup_retention_policies
    try:
        setup_retention_policies()
        return {"status": "ok", "message": "Retention and compression policies configured"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/historian/storage")
async def get_storage() -> dict[str, Any]:
    from historian.client import get_storage_stats
    try:
        return get_storage_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/historian/compress")
async def manual_compress(table: str = "industrial_events", older_than_days: int = 7) -> dict[str, Any]:
    from historian.client import manual_compress_chunk
    try:
        return manual_compress_chunk(table, older_than_days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Alert management endpoints
from alert_manager import alert_manager, AlertState

class AlertCreateRequest(BaseModel):
    asset_id: str
    tag: str
    severity: str
    message: str
    triggered_rules: list[str] = []
    source_event_id: str | None = None

class AlertAcknowledgeRequest(BaseModel):
    alert_id: str
    user_id: str
    note: str | None = None

class AlertEscalateRequest(BaseModel):
    alert_id: str
    user_id: str
    reason: str

class AlertResolveRequest(BaseModel):
    alert_id: str
    user_id: str
    note: str | None = None

@app.post("/api/v1/alerts")
async def create_alert(req: AlertCreateRequest) -> dict[str, Any]:
    try:
        alert = alert_manager.create_alert(
            asset_id=req.asset_id,
            tag=req.tag,
            severity=req.severity,
            message=req.message,
            triggered_rules=req.triggered_rules,
            source_event_id=req.source_event_id,
        )
        return alert
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/alerts/acknowledge")
async def acknowledge_alert(req: AlertAcknowledgeRequest) -> dict[str, Any]:
    try:
        return alert_manager.acknowledge_alert(req.alert_id, req.user_id, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/alerts/escalate")
async def escalate_alert(req: AlertEscalateRequest) -> dict[str, Any]:
    try:
        return alert_manager.escalate_alert(req.alert_id, req.user_id, req.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/alerts/resolve")
async def resolve_alert(req: AlertResolveRequest) -> dict[str, Any]:
    try:
        return alert_manager.resolve_alert(req.alert_id, req.user_id, req.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/alerts")
async def list_alerts(
    state: str | None = None,
    asset_id: str | None = None,
    severity: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return alert_manager.list_alerts(state=state, asset_id=asset_id, severity=severity, limit=limit)

@app.get("/api/v1/alerts/{alert_id}")
async def get_alert(alert_id: str) -> dict[str, Any]:
    alert = alert_manager.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@app.get("/api/v1/alerts/{alert_id}/history")
async def get_alert_history(alert_id: str) -> list[dict[str, Any]]:
    return alert_manager.get_alert_history(alert_id)

@app.get("/api/v1/alerts/statistics")
async def get_alert_statistics() -> dict[str, Any]:
    return alert_manager.get_statistics()

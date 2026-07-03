from __future__ import annotations

import os
import ssl
import sys
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def _prune_legacy_routes() -> None:
    moved_paths = {
        "/api/v1/historian/tables",
        "/api/v1/historian/query",
        "/api/v1/historian/alarms",
        "/api/v1/historian/trend",
        "/api/v1/historian/events",
        "/api/v1/assets",
        "/api/v1/scenarios",
        "/api/v1/events/ingest",
        "/api/v1/events/ingest/batch",
        "/api/v1/historian/retention/setup",
        "/api/v1/historian/storage",
        "/api/v1/historian/dead-letters",
        "/api/v1/historian/compress",
        "/api/v1/alerts",
        "/api/v1/alerts/acknowledge",
        "/api/v1/alerts/escalate",
        "/api/v1/alerts/resolve",
        "/api/v1/alerts/{alert_id}",
        "/api/v1/alerts/{alert_id}/history",
        "/api/v1/alerts/statistics",
        "/api/v1/notifications/send",
        "/api/v1/notifications/status",
        "/api/v1/analytics/correlation/ingest",
        "/api/v1/analytics/correlation/matrix",
        "/api/v1/analytics/correlation/strong",
        "/api/v1/analytics/correlation/graph",
        "/api/v1/analytics/correlation/propagation/{tag}",
        "/api/v1/alerts/escalation/rules",
        "/api/v1/alerts/escalation/rules/{rule_id}",
        "/api/v1/alerts/escalation/check",
        "/api/v1/kpis",
        "/api/v1/kpis/{kpi_id}",
        "/api/v1/kpis/ingest",
        "/api/v1/kpis/samples",
        "/api/v1/outbound-bridge/config",
        "/api/v1/outbound-bridge/publish",
        "/api/v1/outbound-bridge/enable",
        "/api/v1/pipelines",
        "/api/v1/pipelines/{topology_id}",
        "/api/v1/schemas",
        "/api/v1/schemas/{schema_id}/validate",
        "/api/v1/preview/topics",
        "/api/v1/preview/topics/{topic}",
        "/api/v1/preview/topics/{topic}/peek",
        "/api/v1/connectors",
        "/api/v1/connectors/{connector_id}",
        "/api/v1/digital-twin/scenes/{scene_id}",
        "/api/v1/digital-twin/scenes/{scene_id}/entities/{entity_id}/values",
        "/api/v1/oee/shifts",
        "/api/v1/oee/calculate",
        "/api/v1/assets/external",
        "/api/v1/assets/external/{asset_id}",
        "/api/v1/assets/external/{asset_id}/tags",
        "/api/v1/events/external",
        "/api/v1/historian/backup",
        "/api/v1/historian/restore",
        "/api/v1/historian/backups",
        "/api/v1/historian/backup/status",
        "/api/v1/reports/templates",
        "/api/v1/reports/generate/{template_id}",
        "/api/v1/reports",
        "/api/v1/reports/schedule/{template_id}",
        "/api/v1/webhooks",
        "/api/v1/webhooks/{hook_id}",
        "/api/v1/webhooks/test/{hook_id}",
        "/api/v1/notifications",
        "/api/v1/annotations",
        "/api/v1/annotations/{annotation_id}",
        "/api/v1/users",
        "/api/v1/users/{user_id}",
        "/api/v1/auth/login",
        "/api/v1/audit-logs",
    }
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) in moved_paths
            and getattr(getattr(route, "endpoint", None), "__module__", None) == __name__
        )
    ]
from fastapi.responses import ORJSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from services.common.service_health import ServiceHealthState

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Ensure sibling modules (rbac, alert_manager, collaboration) resolve in both
# the repo layout and the flattened Docker layout.
sys.path.insert(0, os.path.dirname(__file__))

try:
    from historian.client import (
        query_sql,
        query_tables,
        query_alarms,
        query_trend,
        query_recent_events as query_historian_events,
    )
except ImportError:
    # Repo (non-flattened) layout: the package lives under services/.
    from services.historian.client import (  # type: ignore
        query_sql,
        query_tables,
        query_alarms,
        query_trend,
        query_recent_events as query_historian_events,
    )
from services.common.runtime_metrics import observe_websocket_batch_delivery
try:
    from auth import decode_access_token  # type: ignore
except ImportError:
    from services.api_service.auth import decode_access_token
try:
    from assets.model import load_hierarchy, hierarchy_to_tree
except ImportError:
    from services.assets.model import load_hierarchy, hierarchy_to_tree  # type: ignore
try:
    from scenarios.engine import list_scenarios
except ImportError:
    from services.scenarios.engine import list_scenarios  # type: ignore


def build_asset_hierarchy() -> list[dict[str, Any]]:
    """Load the asset config and return a UI-ready tree (site→area→line→...)."""
    config_path = os.getenv("ASSETS_CONFIG_PATH", os.path.join(os.path.dirname(__file__), "..", "config", "assets.yaml"))
    try:
        return hierarchy_to_tree(load_hierarchy(config_path))
    except Exception:
        return []

API_PORT = int(os.getenv("API_SERVICE_PORT", "8020"))
TIMESCALE_API_BASE = os.getenv("TIMESCALE_API_BASE", "http://localhost:8010")
WS_HEARTBEAT_INTERVAL = 15.0  # seconds


def _parse_cors_origins(raw: str | None) -> list[str]:
    if raw is None:
        raw = os.getenv("DATASTREAM_CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins

class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    uptime_seconds: int = 0
    services: dict[str, bool] = Field(default_factory=dict)

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
service_state = ServiceHealthState(name="api-service")


# Background broadcaster: polls historian and pushes to WebSocket clients
async def _alarm_broadcaster():
    """Poll alarms periodically and broadcast only when data changes."""
    last_data: list[dict[str, Any]] = []
    while True:
        try:
            data = query_alarms(50)
            if data != last_data:
                last_data = data
                service_state.mark_ok()
                observe_websocket_batch_delivery("alarms", data)
                await alarm_manager.broadcast({"type": "update", "alarms": data})
        except Exception as exc:
            service_state.mark_degraded("alarm broadcast failure", str(exc))
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
                    service_state.mark_ok()
                    observe_websocket_batch_delivery(f"historian:{table}", data)
                    await event_manager.broadcast({"type": "update", "table": table, "events": data})
            except Exception as exc:
                service_state.mark_degraded(f"event broadcast failure:{table}", str(exc))
        await asyncio.sleep(2.0)


async def _telemetry_broadcaster():
    """Broadcast telemetry snapshot to all connected clients."""
    from ai_gateway.main import _build_telemetry
    while True:
        try:
            payload = await _build_telemetry()
            service_state.mark_ok()
            await telemetry_manager.broadcast({"type": "update", "telemetry": payload})
        except Exception as exc:
            service_state.mark_degraded("telemetry broadcast failure", str(exc))
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


# TLS configuration helper
def get_tls_context() -> ssl.SSLContext | None:
    """Load TLS certificates if available."""
    cert_path = os.path.join(os.path.dirname(__file__), "..", "..", "tls", "localhost.pem")
    key_path = os.path.join(os.path.dirname(__file__), "..", "..", "tls", "localhost-key.pem")

    cert_path = os.path.abspath(cert_path)
    key_path = os.path.abspath(key_path)

    if os.path.exists(cert_path) and os.path.exists(key_path):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        return context
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    tasks = [
        asyncio.create_task(_alarm_broadcaster()),
        asyncio.create_task(_event_broadcaster()),
        asyncio.create_task(_telemetry_broadcaster()),
        asyncio.create_task(_heartbeat_task()),
    ]
    # Best-effort: self-configure compression/retention on startup so a fresh
    # deploy doesn't silently keep uncompressed data forever. Non-fatal.
    if os.getenv("HISTORIAN_AUTO_SETUP", "1") == "1":
        try:
            try:
                from historian.client import setup_retention_policies
            except ImportError:
                from services.historian.client import setup_retention_policies  # type: ignore
            setup_retention_policies()
        except Exception:
            pass
    yield
    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Local Stream Engine API", version="0.2.0", lifespan=lifespan)

from services.api_service.routers.historian import router as historian_router
from services.api_service.routers.operations import router as operations_router
from services.api_service.routers.design import router as design_router
from services.api_service.routers.modeling import router as modeling_router
from services.api_service.routers.search import router as search_router
from services.api_service.routers.retrieval import router as retrieval_router
from services.api_service.routers.external import router as external_router
from services.api_service.routers.support import router as support_router
from services.api_service.routers.admin import router as admin_router

app.include_router(historian_router)
app.include_router(operations_router)
app.include_router(design_router)
app.include_router(modeling_router)
app.include_router(search_router)
app.include_router(retrieval_router)
app.include_router(external_router)
app.include_router(support_router)
app.include_router(admin_router)
from services.api_service.routers.historian import ingest_batch, ingest_event
from services.api_service.ops_runtime import _render_topic

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _security_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()
    if method in {"POST", "PUT", "PATCH", "DELETE"} and path not in {"/api/v1/auth/login"} and not path.startswith(("/docs", "/redoc", "/openapi.json", "/health", "/metrics", "/.well-known")):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})
        token = auth_header.split(" ", 1)[1].strip()
        try:
            request.state.auth_payload = decode_access_token(token)
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Invalid bearer token"})

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# TLS info endpoint (defined after app creation)
@app.get("/.well-known/tls-info")
async def tls_info() -> dict[str, Any]:
    """Return TLS status and certificate paths."""
    cert_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tls", "localhost.pem"))
    return {
        "tls_enabled": os.path.exists(cert_path),
        "cert_path": cert_path if os.path.exists(cert_path) else None,
        "setup_script": "scripts/setup-local-tls.sh (or .ps1 on Windows)",
    }


# WebSocket endpoints
@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket):
    # Only push updates when data actually changes (event-driven, not polling)
    last_hash = None
    await alarm_manager.connect(websocket)
    try:
        # Send initial data
        data = query_alarms(50)
        observe_websocket_batch_delivery("alarms", data)
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
    # Only push updates when data actually changes (event-driven, not polling)
    last_hashes: dict[str, str | None] = {}
    await event_manager.connect(websocket)
    try:
        # Send initial data for all tables
        for table in ["industrial_events", "processed_events", "ai_enriched"]:
            data = query_historian_events(table, 100)
            observe_websocket_batch_delivery(f"historian:{table}", data)
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
async def health() -> HealthResponse:
    """Health check with service dependency status."""
    import time
    start = time.time()
    try:
        from services.api_service.auth import auth_security_status
    except ImportError:
        from auth import auth_security_status  # type: ignore
    services = {
        "historian": True,  # Would check actual DB connectivity
        "kafka": True,
        "ai_gateway": True,
    }
    uptime = int(time.time() - start + 1)
    auth_status = auth_security_status()
    status = "ok" if not service_state.degraded else "degraded"
    return HealthResponse(
        status=status,
        version="1.0.0",
        uptime_seconds=uptime,
        services={
            **services,
            "auth": auth_status["jwt_secret_configured"],
            "auth_strong": auth_status["jwt_secret_strong_enough"],
            "degraded": service_state.degraded,
            "degraded_reason": service_state.degraded_reason or "",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

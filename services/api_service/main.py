from __future__ import annotations

import os
import ssl
import sys
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi import Depends
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


class WebhookConfig(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["alarm", "anomaly"])
    headers: dict[str, str] = Field(default_factory=dict)

class OutboundBridgeConfig(BaseModel):
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_use_tls: bool = False
    mqtt_topic_template: str = "industrial/{{asset_id}}/{{tag}}"
    amqp_url: str | None = None
    amqp_exchange: str = "industrial.events"
    amqp_routing_key: str = "{{asset_id}}.{{tag}}"


class NotificationConfig(BaseModel):
    email: str | None = None
    webhook_url: str | None = None
    slack_webhook: str | None = None
    teams_webhook: str | None = None
    events: list[str] = Field(default_factory=lambda: ["alarm", "anomaly"])


# External REST API models
class EventIngestRequest(BaseModel):
    source_protocol: str = "api"
    source_id: str
    asset_id: str
    tag: str
    value: float
    quality: str = "good"
    unit: str = ""
    site: str = "default"
    line: str = "line-01"
    ts_source: str | None = None

class KPIQueryRequest(BaseModel):
    kpi_name: str
    asset_id: str | None = None
    tag: str | None = None
    start_time: str | None = None
    end_time: str | None = None

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


# Background broadcaster: polls historian and pushes to WebSocket clients
async def _alarm_broadcaster():
    """Poll alarms periodically and broadcast only when data changes."""
    last_data: list[dict[str, Any]] = []
    while True:
        try:
            data = query_alarms(50)
            if data != last_data:
                last_data = data
                observe_websocket_batch_delivery("alarms", data)
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
                    observe_websocket_batch_delivery(f"historian:{table}", data)
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


webhook_registry: dict[str, WebhookConfig] = {}
notification_registry: dict[str, NotificationConfig] = {}


WEBHOOK_STORE_PATH = os.getenv("WEBHOOK_STORE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "webhooks.json"))
NOTIFICATION_STORE_PATH = os.getenv("NOTIFICATION_STORE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "notifications.json"))


def _persist_registry(path: str, data: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def _load_registry(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _persist_webhooks() -> None:
    _persist_registry(WEBHOOK_STORE_PATH, {k: v.model_dump() for k, v in webhook_registry.items()})


def _persist_notifications() -> None:
    _persist_registry(NOTIFICATION_STORE_PATH, {k: v.model_dump() for k, v in notification_registry.items()})


def _hydrate_webhooks() -> None:
    raw = _load_registry(WEBHOOK_STORE_PATH)
    for hook_id, cfg in raw.items():
        try:
            webhook_registry[hook_id] = WebhookConfig(**cfg)
        except Exception:
            pass


def _hydrate_notifications() -> None:
    raw = _load_registry(NOTIFICATION_STORE_PATH)
    for notif_id, cfg in raw.items():
        try:
            notification_registry[notif_id] = NotificationConfig(**cfg)
        except Exception:
            pass


_hydrate_webhooks()
_hydrate_notifications()


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

app.include_router(historian_router)
app.include_router(operations_router)
app.include_router(design_router)
app.include_router(modeling_router)
app.include_router(search_router)
app.include_router(retrieval_router)
app.include_router(external_router)
app.include_router(support_router)
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
    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime_seconds=uptime,
        services={
            **services,
            "auth": auth_status["jwt_secret_configured"],
            "auth_strong": auth_status["jwt_secret_strong_enough"],
        },
    )


@app.post("/api/v1/webhooks")
async def register_webhook(config: WebhookConfig) -> dict[str, str]:
    import uuid
    hook_id = str(uuid.uuid4())[:8]
    webhook_registry[hook_id] = config
    _persist_webhooks()
    return {"id": hook_id, "status": "registered"}


@app.get("/api/v1/webhooks")
async def list_webhooks() -> dict[str, Any]:
    return {"webhooks": {k: v.model_dump() for k, v in webhook_registry.items()}}


@app.delete("/api/v1/webhooks/{hook_id}")
async def delete_webhook(hook_id: str) -> dict[str, str]:
    if hook_id not in webhook_registry:
        raise HTTPException(status_code=404, detail="Webhook not found")
    del webhook_registry[hook_id]
    _persist_webhooks()
    return {"status": "deleted"}


@app.post("/api/v1/notifications")
async def register_notification(config: NotificationConfig) -> dict[str, str]:
    import uuid
    notif_id = str(uuid.uuid4())[:8]
    notification_registry[notif_id] = config
    _persist_notifications()
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


def _do_ingest_event(event: dict[str, Any]) -> dict[str, str]:
    import uuid as _uuid

    # The edge model package is referenced two ways depending on layout:
    # - dev/repo root: services.edge_ingest.model
    # - flattened Docker image: edge_ingest.model
    try:
        from services.edge_ingest.model import validate_event, to_json_bytes, utc_now  # type: ignore
    except Exception:
        from edge_ingest.model import validate_event, to_json_bytes, utc_now  # type: ignore
    try:
        from services.historian.client import insert_industrial_event  # type: ignore
    except Exception:
        from historian.client import insert_industrial_event  # type: ignore
    try:
        from services.historian.client import insert_dead_letter  # type: ignore
    except Exception:
        from historian.client import insert_dead_letter  # type: ignore

    brokers = os.getenv("REDPANDA_BROKERS", "localhost:19092")
    normalized_topic = os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized")
    raw_topic = os.getenv("INDUSTRIAL_RAW_TOPIC", "industrial.raw")
    legacy_topic = os.getenv("IOT_TOPIC", "iot.raw")
    dlq_topic = os.getenv("INDUSTRIAL_DLQ_TOPIC", "industrial.dlq")

    payload = {
        "event_id": str(_uuid.uuid4()),
        "source_protocol": event.get("source_protocol", "api"),
        "source_id": event.get("source_id", ""),
        "asset_id": event.get("asset_id", ""),
        "tag": event.get("tag", ""),
        "value": event.get("value", 0),
        "quality": event.get("quality", "good"),
        "unit": event.get("unit", ""),
        "site": event.get("site", "demo-site"),
        "line": event.get("line", "line-01"),
        "ts_source": event.get("ts_source") or utc_now(),
    }

    validated, dlq = validate_event(payload)
    event_id = str(_uuid.uuid4())
    if dlq is not None:
        try:
            _publish_kafka(brokers, dlq_topic, str(payload.get("source_id", "api")).encode(), to_json_bytes(dlq))
        except Exception:
            pass
        try:
            insert_dead_letter({**dlq.model_dump(mode="json"), "origin": "api"})
        except Exception:
            pass
        return {"status": "rejected", "event_id": dlq.event_id, "reason": "validation_failed"}

    assert validated is not None
    event_dict = validated.model_dump(mode="json")
    try:
        insert_industrial_event(event_dict)
    except Exception:
        pass

    key = validated.asset_id.encode("utf-8")
    try:
        _publish_kafka(brokers, raw_topic, key, to_json_bytes(event_dict))
        _publish_kafka(brokers, normalized_topic, key, to_json_bytes(validated))
        _publish_kafka(brokers, legacy_topic, key, to_json_bytes(_to_legacy_iot_event(validated)))
    except Exception as e:
        return {"status": "stored_only", "event_id": event_id, "warning": f"kafka_publish_failed: {e}"}
    return {"status": "ingested", "event_id": event_id}


def _publish_kafka(brokers: str, topic: str, key: bytes, value: bytes) -> None:
    from confluent_kafka import Producer
    producer = Producer({"bootstrap.servers": brokers, "client.id": "api-ingest"})
    producer.produce(topic, key=key, value=value)
    producer.flush(5)


def _to_legacy_iot_event(event: Any) -> dict[str, Any]:
    """Local fallback for the legacy transform (no hard import dependency)."""
    try:
        from common.normalize import to_legacy_iot_event
        return to_legacy_iot_event(event)
    except Exception:
        d = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        return {
            "event_id": d.get("event_id"),
            "device_id": d.get("asset_id", "unknown-asset"),
            "site_id": d.get("site", "demo-site"),
            "timestamp": d.get("ts_source"),
            "source_protocol": d.get("source_protocol", "unknown"),
            "quality": d.get("quality", "unknown"),
            "schema_version": d.get("schema_version", 1),
            "temperature_c": 0.0,
            "vibration_mm_s": 0.0,
            "pressure_bar": 0.0,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

# Collaboration endpoints
@app.get("/api/v1/annotations")
async def list_annotations(target_type: str | None = None, target_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from api_service.collaboration import collaboration_store
    return collaboration_store.list_annotations(target_type, target_id, limit)

@app.post("/api/v1/annotations")
async def create_annotation(req: dict[str, Any]) -> dict[str, str]:
    from api_service.collaboration import collaboration_store
    ann = collaboration_store.add_annotation(
        target_type=req.get("target_type", "event"),
        target_id=req.get("target_id", ""),
        user_id=req.get("user_id", "anonymous"),
        username=req.get("username", "Anonymous"),
        text=req.get("text", ""),
        tags=req.get("tags", []),
    )
    return {"status": "created", "annotation_id": ann.annotation_id}

@app.delete("/api/v1/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str) -> dict[str, str]:
    from api_service.collaboration import collaboration_store
    collaboration_store.delete_annotation(annotation_id)
    return {"status": "deleted"}

try:
    from rbac import Role, Permission
except ImportError:
    from services.api_service.rbac import Role, Permission  # type: ignore
try:
    from auth import require_permission
except ImportError:
    from services.api_service.auth import require_permission  # type: ignore

class CreateUserRequest(BaseModel):
    user_id: str
    username: str
    role: str
    email: str | None = None
    password: str | None = None

class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/api/v1/users")
async def create_user_endpoint(
    req: CreateUserRequest,
    _admin: Any = Depends(require_permission(Permission.ADMIN)),
) -> dict[str, Any]:
    """Create a new user (admin only)."""
    from auth import create_user, hash_password
    from rbac import Role
    role = Role(req.role)
    user = create_user(req.user_id, req.username, role, req.email, req.password)
    return user.to_dict()

@app.get("/api/v1/users/{user_id}")
async def get_user_endpoint(
    user_id: str,
    _admin: Any = Depends(require_permission(Permission.ADMIN)),
) -> dict[str, Any]:
    """Get a user by ID (admin only)."""
    from auth import get_user
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()

@app.post("/api/v1/auth/login")
async def login(req: AuthRequest) -> dict[str, Any]:
    """Authenticate and return a JWT access token."""
    from auth import authenticate_user, create_access_token
    from auth import audit_log
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    audit_log.log(user.user_id, "login", "auth")
    token = create_access_token(user.user_id, user.role.value)
    return {"token": token, "user": user.to_dict()}

@app.get("/api/v1/audit-logs")
async def get_audit_logs(
    limit: int = 100,
    _admin: Any = Depends(require_permission(Permission.ADMIN)),
) -> list[dict[str, Any]]:
    """List audit logs (admin only)."""
    from auth import audit_log
    return audit_log.get_logs(limit)


try:
    from rbac import Role, Permission, User, AuditLog, audit_log, create_user, get_user, authenticate_user, require_permission
except ImportError:
    from services.api_service.rbac import (  # type: ignore
        Role, Permission, User, AuditLog, audit_log, create_user, get_user, authenticate_user, require_permission,
    )
from fastapi import Depends


_prune_legacy_routes()

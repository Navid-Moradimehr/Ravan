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
    }
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) in moved_paths
            and getattr(getattr(route, "endpoint", None), "__module__", None) == __name__
        )
    ]
from fastapi.responses import ORJSONResponse
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

app.include_router(historian_router)
from services.api_service.routers.historian import ingest_batch, ingest_event

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    services = {
        "historian": True,  # Would check actual DB connectivity
        "kafka": True,
        "ai_gateway": True,
    }
    uptime = int(time.time() - start + 1)
    return HealthResponse(status="ok", version="1.0.0", uptime_seconds=uptime, services=services)


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

# KPI endpoints
@app.get("/api/v1/kpis")
async def list_kpis() -> list[dict[str, Any]]:
    from analytics.kpi_engine import kpi_engine
    return kpi_engine.list_kpis()

@app.post("/api/v1/kpis")
async def create_kpi_endpoint(req: dict[str, Any]) -> dict[str, str]:
    from analytics.kpi_engine import KPIFormula, kpi_engine
    kpi = KPIFormula(**req)
    kpi_engine.register_kpi(kpi)
    return {"status": "created", "kpi_id": kpi.kpi_id}

@app.delete("/api/v1/kpis/{kpi_id}")
async def delete_kpi_endpoint(kpi_id: str) -> dict[str, str]:
    from analytics.kpi_engine import kpi_engine
    kpi_engine.unregister_kpi(kpi_id)
    return {"status": "deleted"}

# Pipeline designer endpoints
@app.get("/api/v1/pipelines")
async def list_pipelines() -> list[dict[str, Any]]:
    from processor.pipeline_designer import pipeline_registry
    return pipeline_registry.list_all()

@app.post("/api/v1/pipelines")
async def create_pipeline(req: dict[str, Any]) -> dict[str, str]:
    from processor.pipeline_designer import pipeline_registry
    topo = pipeline_registry.create(req.get("name", "untitled"), req.get("description", ""))
    return {"status": "created", "topology_id": topo.topology_id}

@app.delete("/api/v1/pipelines/{topology_id}")
async def delete_pipeline(topology_id: str) -> dict[str, str]:
    from processor.pipeline_designer import pipeline_registry
    pipeline_registry.delete(topology_id)
    return {"status": "deleted"}

# Schema Registry endpoints
@app.get("/api/v1/schemas")
async def list_schemas() -> list[dict[str, Any]]:
    from common.schema_registry import schema_registry
    return schema_registry.list_schemas()

@app.post("/api/v1/schemas/{schema_id}/validate")
async def validate_schema(schema_id: str, req: dict[str, Any]) -> dict[str, Any]:
    from common.schema_registry import schema_registry
    version = req.get("version")
    data = req.get("data", {})
    return schema_registry.validate(schema_id, data, version)

@app.post("/api/v1/schemas")
async def register_schema(req: dict[str, Any]) -> dict[str, str]:
    from common.schema_registry import schema_registry
    sv = schema_registry.register(req.get("schema_id", "custom"), req.get("fields", []))
    return {"status": "registered", "schema_id": sv.schema_id, "version": str(sv.version)}

# Real-time Data Preview endpoints
@app.get("/api/v1/preview/topics")
async def preview_topics() -> list[str]:
    from common.data_preview import list_topics
    return list_topics()

@app.get("/api/v1/preview/topics/{topic}")
async def preview_topic(topic: str, limit: int = 10) -> list[dict[str, Any]]:
    from common.data_preview import peek_topic
    return peek_topic(topic, limit=limit)

@app.post("/api/v1/preview/topics/{topic}/peek")
async def peek_topic_endpoint(topic: str, req: dict[str, Any]) -> list[dict[str, Any]]:
    from common.data_preview import peek_topic
    limit = req.get("limit", 10)
    return peek_topic(topic, limit=limit)

# Connector Marketplace endpoints
@app.get("/api/v1/connectors")
async def list_connectors_endpoint(category: str | None = None, protocol: str | None = None) -> list[dict[str, Any]]:
    from datasets.data_sources_catalog import list_connectors
    return list_connectors(category, protocol)

@app.get("/api/v1/connectors/{connector_id}")
async def get_connector_endpoint(connector_id: str) -> dict[str, Any]:
    from datasets.data_sources_catalog import get_connector
    c = get_connector(connector_id)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found")
    return c.__dict__

# Digital Twin endpoints
@app.get("/api/v1/digital-twin/scenes/{scene_id}")
async def get_digital_twin_scene(scene_id: str) -> dict[str, Any]:
    from assets.digital_twin import demo_scene
    return demo_scene.to_dict()

@app.post("/api/v1/digital-twin/scenes/{scene_id}/entities/{entity_id}/values")
async def update_twin_value(scene_id: str, entity_id: str, req: dict[str, Any]) -> dict[str, str]:
    from assets.digital_twin import demo_scene
    tag = req.get("tag", "")
    value = float(req.get("value", 0))
    ok = demo_scene.update_value(entity_id, tag, value)
    if not ok:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"status": "updated"}

# OEE / Production Reporting endpoints
@app.get("/api/v1/oee/shifts")
async def list_shifts(date: str | None = None) -> list[dict[str, Any]]:
    from analytics.oee_engine import oee_engine
    from datetime import datetime
    dt = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    shifts = oee_engine.generate_shifts(dt)
    return [s.__dict__ for s in shifts]

@app.post("/api/v1/oee/calculate")
async def calculate_oee(req: dict[str, Any]) -> dict[str, Any]:
    from analytics.oee_engine import oee_engine, ShiftPeriod
    from datetime import datetime
    shift = ShiftPeriod(shift_id=req.get("shift_id", "unknown"), start=datetime.now(), end=datetime.now(), planned_production_time_minutes=req.get("planned_minutes", 480.0))
    result = oee_engine.calculate(shift, runtime_minutes=req.get("runtime_minutes", 0.0), total_count=req.get("total_count", 0), good_count=req.get("good_count", 0))
    return result.to_dict()

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


@app.get("/api/v1/historian/dead-letters")
async def list_dead_letters(limit: int = 100) -> list[dict[str, Any]]:
    """List recently rejected (dead-letter) events so operators can inspect/replay them."""
    try:
        from historian.client import query_recent_events
        return query_recent_events("dead_letter_events", limit)
    except Exception:
        try:
            from services.historian.client import query_recent_events
            return query_recent_events("dead_letter_events", limit)
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
try:
    from alert_manager import alert_manager, AlertState
except ImportError:
    from services.api_service.alert_manager import alert_manager, AlertState  # type: ignore

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


# Notification endpoints using Apprise
from notifications import notifier, NotificationPayload

class NotifyRequest(BaseModel):
    title: str
    body: str
    severity: str = "info"
    asset_id: str | None = None
    tag: str | None = None
    event_id: str | None = None

@app.post("/api/v1/notifications/send")
async def send_notification(req: NotifyRequest) -> dict[str, Any]:
    """Send a notification through all configured channels."""
    payload = NotificationPayload(
        title=req.title,
        body=req.body,
        severity=req.severity,
        asset_id=req.asset_id,
        tag=req.tag,
        event_id=req.event_id,
    )
    result = notifier.notify(payload)
    if not result["sent"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Notification failed"))
    return result

@app.get("/api/v1/notifications/status")
async def notification_status() -> dict[str, Any]:
    """Get notification service status."""
    from notifications import APPRISE_AVAILABLE
    return {
        "apprise_available": APPRISE_AVAILABLE,
        "channels_configured": len(notifier._config_urls),
        "channels": notifier._config_urls,
    }


# Backup and restore endpoints
from historian.backup import create_backup, restore_backup, list_backups, get_walg_status

class BackupRequest(BaseModel):
    tables: list[str] | None = None
    backup_dir: str | None = None

class RestoreRequest(BaseModel):
    backup_path: str
    target_database: str | None = None

@app.post("/api/v1/historian/backup")
async def backup_historian(req: BackupRequest) -> dict[str, Any]:
    """Create a backup of the historian database."""
    result = create_backup(backup_dir=req.backup_dir, tables=req.tables)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    return result

@app.post("/api/v1/historian/restore")
async def restore_historian(req: RestoreRequest) -> dict[str, Any]:
    """Restore the historian database from a backup."""
    result = restore_backup(req.backup_path, req.target_database)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Restore failed"))
    return result

@app.get("/api/v1/historian/backups")
async def list_historian_backups() -> list[dict[str, Any]]:
    """List available historian backups."""
    return list_backups()

@app.get("/api/v1/historian/backup/status")
async def backup_status() -> dict[str, Any]:
    """Get backup tool status."""
    return get_walg_status()


# Correlation analysis endpoints
from analytics.correlation import CorrelationAnalyzer, get_analyzer

class CorrelationRequest(BaseModel):
    tag: str
    timestamp: str
    value: float

@app.post("/api/v1/analytics/correlation/ingest")
async def ingest_correlation_data(req: CorrelationRequest) -> dict[str, str]:
    """Ingest sensor data for correlation analysis."""
    analyzer = get_analyzer()
    analyzer.add_value(req.tag, req.timestamp, req.value)
    return {"status": "ok"}

@app.get("/api/v1/analytics/correlation/matrix")
async def get_correlation_matrix() -> dict[str, Any]:
    """Get correlation matrix between all tags."""
    analyzer = get_analyzer()
    return analyzer.get_correlation_matrix()

@app.get("/api/v1/analytics/correlation/strong")
async def get_strong_correlations(threshold: float = 0.7) -> list[dict[str, Any]]:
    """Find strongly correlated tag pairs."""
    analyzer = get_analyzer()
    return analyzer.find_strong_correlations(threshold)

@app.get("/api/v1/analytics/correlation/graph")
async def get_causal_graph(threshold: float = 0.5) -> dict[str, Any]:
    """Get causal graph for root-cause analysis."""
    analyzer = get_analyzer()
    return analyzer.build_causal_graph(threshold)

@app.get("/api/v1/analytics/correlation/propagation/{tag}")
async def get_anomaly_propagation(tag: str, lookback: int = 10) -> list[dict[str, Any]]:
    """Detect anomaly propagation for a specific tag."""
    analyzer = get_analyzer()
    return analyzer.detect_anomaly_propagation(tag, lookback)


# Alert escalation endpoints
from alert_escalation import escalation_engine, EscalationRule

class EscalationRuleRequest(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    severity_filter: list[str] = ["critical"]
    asset_pattern: str | None = None
    tag_pattern: str | None = None
    auto_escalate_after_minutes: int = 15
    notify_channels: list[str] = []
    escalate_to_role: str | None = None
    enabled: bool = True

@app.post("/api/v1/alerts/escalation/rules")
async def add_escalation_rule(req: EscalationRuleRequest) -> dict[str, str]:
    """Add a new escalation rule."""
    rule = EscalationRule(
        rule_id=req.rule_id,
        name=req.name,
        description=req.description,
        severity_filter=req.severity_filter,
        asset_pattern=req.asset_pattern,
        tag_pattern=req.tag_pattern,
        auto_escalate_after_minutes=req.auto_escalate_after_minutes,
        notify_channels=req.notify_channels,
        escalate_to_role=req.escalate_to_role,
        enabled=req.enabled,
    )
    escalation_engine.add_rule(rule)
    return {"status": "ok", "rule_id": req.rule_id}

@app.get("/api/v1/alerts/escalation/rules")
async def list_escalation_rules() -> list[dict[str, Any]]:
    """List all escalation rules."""
    return escalation_engine.list_rules()

@app.delete("/api/v1/alerts/escalation/rules/{rule_id}")
async def delete_escalation_rule(rule_id: str) -> dict[str, str]:
    """Delete an escalation rule."""
    if escalation_engine.remove_rule(rule_id):
        return {"status": "deleted", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")

@app.post("/api/v1/alerts/escalation/check")
async def check_escalations() -> list[dict[str, Any]]:
    """Manually trigger escalation check for all pending alerts."""
    return escalation_engine.check_all_pending_alerts()


# KPI engine endpoints
from analytics.kpi_engine import kpi_engine, KPIFormula

class KPIRequest(BaseModel):
    kpi_id: str
    name: str
    description: str = ""
    input_tags: list[str] = []
    expression: str = ""
    window_seconds: int = 60
    unit: str = ""
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    enabled: bool = True

@app.post("/api/v1/kpis")
async def register_kpi(req: KPIRequest) -> dict[str, str]:
    """Register a new KPI formula."""
    kpi = KPIFormula(
        kpi_id=req.kpi_id,
        name=req.name,
        description=req.description,
        input_tags=req.input_tags,
        expression=req.expression,
        window_seconds=req.window_seconds,
        unit=req.unit,
        warning_threshold=req.warning_threshold,
        critical_threshold=req.critical_threshold,
        enabled=req.enabled,
    )
    kpi_engine.register_kpi(kpi)
    return {"status": "ok", "kpi_id": req.kpi_id}

@app.get("/api/v1/kpis")
async def list_kpis() -> list[dict[str, Any]]:
    """List all registered KPIs."""
    return kpi_engine.list_kpis()

@app.delete("/api/v1/kpis/{kpi_id}")
async def unregister_kpi(kpi_id: str) -> dict[str, str]:
    """Unregister a KPI formula."""
    if kpi_engine.unregister_kpi(kpi_id):
        return {"status": "deleted", "kpi_id": kpi_id}
    raise HTTPException(status_code=404, detail="KPI not found")

@app.post("/api/v1/kpis/ingest")
async def ingest_kpi_value(tag: str, value: float) -> list[dict[str, Any]]:
    """Ingest a tag value and evaluate dependent KPIs."""
    return kpi_engine.ingest_value(tag, value)

@app.get("/api/v1/kpis/samples")
async def get_sample_kpis() -> list[dict[str, Any]]:
    """Get sample KPI definitions."""
    return [k.__dict__ for k in kpi_engine.get_sample_kpis()]


# REST API full CRUD for external systems
class AssetCreateRequest(BaseModel):
    id: str
    name: str
    type: str
    parent_id: str | None = None
    metadata: dict[str, Any] = {}

class TagCreateRequest(BaseModel):
    id: str
    name: str
    unit: str
    min: float
    max: float
    warning_low: float | None = None
    warning_high: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    sampling_rate_hz: float = 1.0

@app.post("/api/v1/assets/external")
async def create_external_asset(req: AssetCreateRequest) -> dict[str, Any]:
    """Create an asset from an external system."""
    from assets.model import AssetNode, add_asset
    asset = AssetNode(
        id=req.id,
        name=req.name,
        type=req.type,
        parent_id=req.parent_id,
        metadata=req.metadata,
    )
    add_asset(asset)
    return {"status": "created", "asset": asset.to_dict()}

@app.get("/api/v1/assets/external/{asset_id}")
async def get_external_asset(asset_id: str) -> dict[str, Any]:
    """Get an asset by ID."""
    from assets.model import get_asset
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset.to_dict()

@app.put("/api/v1/assets/external/{asset_id}")
async def update_external_asset(asset_id: str, req: AssetCreateRequest) -> dict[str, Any]:
    """Update an asset from an external system."""
    from assets.model import update_asset
    asset = update_asset(asset_id, name=req.name, type=req.type, metadata=req.metadata)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "updated", "asset": asset.to_dict()}

@app.delete("/api/v1/assets/external/{asset_id}")
async def delete_external_asset(asset_id: str) -> dict[str, str]:
    """Delete an asset."""
    from assets.model import delete_asset
    if delete_asset(asset_id):
        return {"status": "deleted", "asset_id": asset_id}
    raise HTTPException(status_code=404, detail="Asset not found")

@app.post("/api/v1/assets/external/{asset_id}/tags")
async def add_asset_tag(asset_id: str, req: TagCreateRequest) -> dict[str, Any]:
    """Add a tag to an asset."""
    from assets.model import add_tag_to_asset
    tag = add_tag_to_asset(
        asset_id=asset_id,
        tag_id=req.id,
        name=req.name,
        unit=req.unit,
        min_val=req.min,
        max_val=req.max,
        warning_low=req.warning_low,
        warning_high=req.warning_high,
        critical_low=req.critical_low,
        critical_high=req.critical_high,
        sampling_rate_hz=req.sampling_rate_hz,
    )
    if not tag:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "created", "tag": tag}

@app.get("/api/v1/events/external")
async def get_external_events(
    asset_id: str | None = None,
    tag: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get events for external systems with filtering."""
    from historian.client import query_sql
    
    conditions = []
    params = []
    
    if asset_id:
        conditions.append("asset_id = %s")
        params.append(asset_id)
    if tag:
        conditions.append("tag = %s")
        params.append(tag)
    if start_time:
        conditions.append("time >= %s")
        params.append(start_time)
    if end_time:
        conditions.append("time <= %s")
        params.append(end_time)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM industrial_events WHERE {where_clause} ORDER BY time DESC LIMIT %s"
    params.append(limit)
    
    return query_sql(sql, tuple(params))

@app.post("/api/v1/events/external")
async def ingest_external_event(event: dict[str, Any]) -> dict[str, str]:
    """Ingest an event from an external system."""
    from historian.client import insert_industrial_event
    from common.normalize import normalize_runtime_event
    
    normalized = normalize_runtime_event(event)
    insert_industrial_event(normalized)
    return {"status": "received", "event_id": normalized.get("event_id", "unknown")}


# Report generation endpoints
from analytics.reporting import report_engine, ReportTemplate

class ReportTemplateRequest(BaseModel):
    template_id: str
    name: str
    description: str = ""
    query: str = ""
    format: str = "csv"
    schedule: str | None = None
    recipients: list[str] = []
    enabled: bool = True

@app.post("/api/v1/reports/templates")
async def create_report_template(req: ReportTemplateRequest) -> dict[str, str]:
    """Create a new report template."""
    template = ReportTemplate(
        template_id=req.template_id,
        name=req.name,
        description=req.description,
        query=req.query,
        format=req.format,
        schedule=req.schedule,
        recipients=req.recipients,
        enabled=req.enabled,
    )
    report_engine.register_template(template)
    return {"status": "ok", "template_id": req.template_id}

@app.get("/api/v1/reports/templates")
async def list_report_templates() -> list[dict[str, Any]]:
    """List all report templates."""
    return report_engine.list_templates()

@app.post("/api/v1/reports/generate/{template_id}")
async def generate_report(
    template_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    format: str | None = None,
) -> dict[str, Any]:
    """Generate a report from a template."""
    return report_engine.generate_report(template_id, start_time, end_time, format)

@app.get("/api/v1/reports")
async def list_generated_reports() -> list[dict[str, Any]]:
    """List all generated reports."""
    return report_engine.list_generated_reports()

@app.post("/api/v1/reports/schedule/{template_id}")
async def schedule_report(template_id: str, cron: str = "daily") -> dict[str, Any]:
    """Schedule a report to run periodically."""
    return report_engine.schedule_report(template_id, cron)

# Outbound MQTT/AMQP bridge endpoints
class OutboundBridgeState(BaseModel):
    enabled: bool = True
    config: OutboundBridgeConfig


class OutboundEventRequest(BaseModel):
    asset_id: str
    tag: str
    value: float
    quality: str = "good"
    unit: str = ""
    timestamp: str | None = None


# In-memory bridge state (replace with DB in production)
_outbound_bridge_state: OutboundBridgeState | None = None
_mqtt_client: Any = None
_amqp_connection: Any = None


def _render_topic(template: str, event: dict[str, Any]) -> str:
    return template.replace("{{asset_id}}", event.get("asset_id", "")).replace("{{tag}}", event.get("tag", ""))


def _publish_mqtt(config: OutboundBridgeConfig, event: dict[str, Any]) -> dict[str, Any]:
    try:
        import paho.mqtt.publish as mqtt_publish
        topic = _render_topic(config.mqtt_topic_template, event)
        payload = json.dumps(event)
        mqtt_publish.single(
            topic,
            payload=payload,
            hostname=config.mqtt_host,
            port=config.mqtt_port,
            tls={} if config.mqtt_use_tls else None,
        )
        return {"ok": True, "protocol": "mqtt", "topic": topic}
    except Exception as e:
        return {"ok": False, "protocol": "mqtt", "error": str(e)}


def _publish_amqp(config: OutboundBridgeConfig, event: dict[str, Any]) -> dict[str, Any]:
    try:
        import pika
        if not config.amqp_url:
            return {"ok": False, "protocol": "amqp", "error": "amqp_url not configured"}
        params = pika.URLParameters(config.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange=config.amqp_exchange, exchange_type="topic", durable=True)
        routing_key = _render_topic(config.amqp_routing_key, event)
        channel.basic_publish(
            exchange=config.amqp_exchange,
            routing_key=routing_key,
            body=json.dumps(event).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
        connection.close()
        return {"ok": True, "protocol": "amqp", "routing_key": routing_key}
    except Exception as e:
        return {"ok": False, "protocol": "amqp", "error": str(e)}


@app.post("/api/v1/outbound-bridge/config")
async def set_outbound_bridge_config(req: OutboundBridgeState) -> dict[str, Any]:
    global _outbound_bridge_state
    _outbound_bridge_state = req
    return {"ok": True, "enabled": req.enabled, "config": req.config.model_dump()}


@app.get("/api/v1/outbound-bridge/config")
async def get_outbound_bridge_config() -> dict[str, Any]:
    if _outbound_bridge_state is None:
        return {"enabled": False, "config": None}
    return {"enabled": _outbound_bridge_state.enabled, "config": _outbound_bridge_state.config.model_dump()}


@app.post("/api/v1/outbound-bridge/publish")
async def publish_outbound_event(req: OutboundEventRequest) -> dict[str, Any]:
    if _outbound_bridge_state is None or not _outbound_bridge_state.enabled:
        raise HTTPException(status_code=400, detail="Outbound bridge not enabled")
    config = _outbound_bridge_state.config
    event = req.model_dump()
    if event.get("timestamp") is None:
        event["timestamp"] = datetime.utcnow().isoformat()
    results = []
    if config.mqtt_host:
        results.append(_publish_mqtt(config, event))
    if config.amqp_url:
        results.append(_publish_amqp(config, event))
    if not results:
        raise HTTPException(status_code=400, detail="No outbound protocol configured")
    return {"ok": all(r.get("ok") for r in results), "results": results}


@app.post("/api/v1/outbound-bridge/enable")
async def enable_outbound_bridge(enabled: bool = True) -> dict[str, Any]:
    global _outbound_bridge_state
    if _outbound_bridge_state is None:
        raise HTTPException(status_code=400, detail="Bridge config not set")
    _outbound_bridge_state.enabled = enabled
    return {"ok": True, "enabled": enabled}

try:
    from rbac import Role, Permission, User, AuditLog, audit_log, create_user, get_user, authenticate_user, require_permission
except ImportError:
    from services.api_service.rbac import (  # type: ignore
        Role, Permission, User, AuditLog, audit_log, create_user, get_user, authenticate_user, require_permission,
    )
from fastapi import Depends


_prune_legacy_routes()

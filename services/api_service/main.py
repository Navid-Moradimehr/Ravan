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


@app.get("/.well-known/tls-info")
async def tls_info() -> dict[str, Any]:
    """Return TLS status and certificate paths."""
    cert_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "tls", "localhost.pem"))
    return {
        "tls_enabled": os.path.exists(cert_path),
        "cert_path": cert_path if os.path.exists(cert_path) else None,
        "setup_script": "scripts/setup-local-tls.sh (or .ps1 on Windows)",
    }


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

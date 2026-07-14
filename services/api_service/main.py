from __future__ import annotations

import os
import ssl
import sys
import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
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
        "/api/v1/connections",
        "/api/v1/connections/{connection_id}",
        "/api/v1/connections/{connection_id}/enable",
        "/api/v1/connections/{connection_id}/disable",
        "/api/v1/connections/{connection_id}/validate",
        "/api/v1/connections/{connection_id}/test",
        "/api/v1/connections/{connection_id}/preview",
        "/api/v1/observability/source-health",
        "/api/v1/sinks",
        "/api/v1/sinks/{route_id}",
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
        "/api/v1/notifications/{notification_id}",
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

from services.api_service.realtime import create_realtime_tasks, router as realtime_router, service_state


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
    services: dict[str, Any] = Field(default_factory=dict)


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
    tasks = create_realtime_tasks()
    policy_stop = None
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
    try:
        from services.common.threshold_policy import list_threshold_policies
        from services.common.threshold_policy_sync import start_policy_sync_workers

        policy_stop, _policy_threads = start_policy_sync_workers(
            role="api-service",
            enable_relay=True,
            initial_bootstrap=lambda: list_threshold_policies()["policies"],
        )
    except Exception:
        policy_stop = None
    yield
    if policy_stop is not None:
        policy_stop.set()
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
from services.api_service.routers.connections import router as connections_router
from services.api_service.routers.sinks import router as sinks_router
from services.api_service.routers.modeling import router as modeling_router
from services.api_service.routers.ai_reporting import router as ai_reporting_router
from services.api_service.routers.search import router as search_router
from services.api_service.routers.retrieval import router as retrieval_router
from services.api_service.routers.metadata import router as metadata_router
from services.api_service.routers.asset_registry import router as asset_registry_router
from services.api_service.routers.threshold_policies import router as threshold_policies_router
from services.api_service.routers.event_catalog import router as event_catalog_router
from services.api_service.routers.governance import router as governance_router
from services.api_service.routers.operational_memory import router as operational_memory_router
from services.api_service.routers.observability import router as observability_router
from services.api_service.routers.lineage import router as lineage_router
from services.api_service.routers.semantic import router as semantic_router
from services.api_service.routers.external import router as external_router
from services.api_service.routers.operational_events import router as operational_events_router
from services.api_service.routers.support import router as support_router
from services.api_service.routers.admin import router as admin_router
from services.api_service.routers.historian import ingest_batch, ingest_event

app.include_router(historian_router)
app.include_router(operations_router)
app.include_router(design_router)
app.include_router(connections_router)
app.include_router(sinks_router)
app.include_router(modeling_router)
app.include_router(ai_reporting_router)
app.include_router(search_router)
app.include_router(retrieval_router)
app.include_router(metadata_router)
app.include_router(asset_registry_router)
app.include_router(threshold_policies_router)
app.include_router(event_catalog_router)
app.include_router(governance_router)
app.include_router(operational_memory_router)
app.include_router(observability_router)
app.include_router(lineage_router)
app.include_router(semantic_router)
app.include_router(external_router)
app.include_router(operational_events_router)
app.include_router(support_router)
app.include_router(admin_router)
app.include_router(realtime_router)
from services.api_service.ops_runtime import _render_topic


def _persist_webhooks() -> None:
    """Compatibility hook kept for tests and existing callers."""
    return None

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
    exempt_mutations = {
        "/api/v1/auth/login",
        "/api/v1/historian/replay",
    }
    if method in {"POST", "PUT", "PATCH", "DELETE"} and path not in exempt_mutations and not path.startswith(("/docs", "/redoc", "/openapi.json", "/health", "/metrics", "/.well-known")):
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


@app.get("/health")
async def health() -> HealthResponse:
    """Health check with real dependency probes.

    Each dependency (kafka, historian, ai_gateway) is probed over the network
    with a short timeout so a slow/dead dependency surfaces as ``False`` without
    hanging the endpoint. The overall status is ``degraded`` if any probed
    dependency is down or the service is in a degraded state.
    """
    import time

    from services.api_service.health_probes import (
        probe_ai_gateway,
        probe_historian,
        probe_kafka,
    )

    start = time.time()
    try:
        from services.api_service.auth import auth_security_status
    except ImportError:
        from auth import auth_security_status  # type: ignore

    # Probes are independent. Running them concurrently keeps a slow local
    # model or historian from serially extending the health response.
    try:
        kafka_ok, historian_ok, ai_ok = await asyncio.wait_for(
            asyncio.gather(
                asyncio.to_thread(probe_kafka),
                asyncio.to_thread(probe_historian),
                asyncio.to_thread(probe_ai_gateway),
            ),
            timeout=2.5,
        )
    except asyncio.TimeoutError:
        # A health endpoint must remain useful when a dependency probe itself
        # misbehaves. The next request can retry while this one reports the
        # dependency state conservatively.
        kafka_ok = historian_ok = ai_ok = False

    auth_status = auth_security_status()
    dep_down = not (kafka_ok and historian_ok and ai_ok)
    status = "degraded" if (service_state.degraded or dep_down) else "ok"
    return HealthResponse(
        status=status,
        version="1.0.0",
        uptime_seconds=int(time.time() - start + 1),
        services={
            "historian": historian_ok,
            "kafka": kafka_ok,
            "ai_gateway": ai_ok,
            "auth": auth_status["jwt_secret_configured"],
            "auth_strong": auth_status["jwt_secret_strong_enough"],
            "degraded": service_state.degraded,
            "degraded_reason": service_state.degraded_reason or "",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

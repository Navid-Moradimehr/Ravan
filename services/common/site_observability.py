from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from services.api_service.health_probes import probe_ai_gateway, probe_historian, probe_kafka
from services.common.site_profiles import load_site_profile, validate_site_profile
from services.historian.backup import get_walg_status


@dataclass(frozen=True)
class ObservabilitySignal:
    name: str
    source: str
    status: str
    value: Any = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slo_targets(deployment_mode: str) -> dict[str, Any]:
    targets = {
        "processing_lag_messages": 1000,
        "ai_latency_p95_seconds": 5.0,
        "historian_write_p95_seconds": 2.0,
        "websocket_delivery_p95_seconds": 2.0,
        "dlq_rate_per_second": 0.0,
    }
    if deployment_mode == "federated":
        return {
            "ingest_availability_percent": 99.5,
            "ai_fallback_availability_percent": 100.0,
            "historian_backup_success_percent": 99.0,
            "broker_health_target": "healthy",
            "api_health_target": "healthy_or_degraded_with_reason",
            **targets,
        }
    if deployment_mode == "plant-local":
        return {
            "ingest_availability_percent": 99.5,
            "ai_fallback_availability_percent": 100.0,
            "historian_backup_success_percent": 99.0,
            "broker_health_target": "healthy",
            "api_health_target": "healthy_or_degraded_with_reason",
            **targets,
        }
    return {
        "ingest_availability_percent": 99.0,
        "ai_fallback_availability_percent": 100.0,
        "historian_backup_success_percent": 99.0,
        "broker_health_target": "healthy",
        "api_health_target": "healthy_or_degraded_with_reason",
        **targets,
    }


def _timed_probe(probe: Any) -> tuple[bool, float]:
    started = time.perf_counter()
    try:
        result = bool(probe())
    except Exception:
        result = False
    return result, round((time.perf_counter() - started) * 1000, 3)


def _prometheus_query(query: str) -> float | None:
    base = os.getenv("PROMETHEUS_URL", "http://localhost:19090").rstrip("/")
    try:
        response = httpx.get(f"{base}/api/v1/query", params={"query": query}, timeout=1.5)
        response.raise_for_status()
        result = response.json().get("data", {}).get("result", [])
        if not result:
            return None
        return float(result[0].get("value", [None, None])[1])
    except (ValueError, TypeError, KeyError, httpx.HTTPError):
        return None


def _slo_evaluation(deployment_mode: str = "single-site") -> dict[str, Any]:
    """Evaluate only measured Prometheus values; unavailable is not healthy."""

    queries = {
        "processing_lag_messages": "max(datastream_broker_consumer_lag_messages)",
        "ai_latency_p95_seconds": "histogram_quantile(0.95, sum(rate(ai_gateway_llm_request_seconds_bucket[5m])) by (le))",
        "historian_write_p95_seconds": "histogram_quantile(0.95, sum(rate(datastream_fanout_write_latency_seconds_bucket[5m])) by (le))",
        "websocket_delivery_p95_seconds": "histogram_quantile(0.95, sum(rate(datastream_websocket_delivery_lag_seconds_bucket[5m])) by (le))",
        "dlq_rate_per_second": "sum(rate(edge_ingest_dlq_total[5m]))",
    }
    # Keep an unavailable Prometheus from multiplying the timeout across the
    # whole release gate. The evidence set is fixed and safe to probe in
    # parallel.
    with ThreadPoolExecutor(max_workers=len(queries), thread_name_prefix="slo-probe") as executor:
        futures = {name: executor.submit(_prometheus_query, query) for name, query in queries.items()}
        measurements = {}
        for name, future in futures.items():
            try:
                measurements[name] = future.result(timeout=2.0)
            except Exception:
                # A slow or broken metrics endpoint is unknown evidence, not
                # an observability API failure.
                measurements[name] = None
    targets = _slo_targets(deployment_mode)
    checks = []
    for name, observed in measurements.items():
        target = targets[name]
        if observed is None:
            checks.append({"name": name, "status": "unknown", "observed": None, "target": target, "notes": "Prometheus has no usable value for this measurement"})
        else:
            checks.append({"name": name, "status": "passed" if observed <= target else "failed", "observed": observed, "target": target, "notes": "lower is better"})
    return {
        "status": "passed" if checks and all(item["status"] == "passed" for item in checks) else "unknown" if any(item["status"] == "unknown" for item in checks) else "failed",
        "measurements": checks,
        "source": "prometheus",
        "notes": "Unknown measurements are not treated as healthy evidence.",
    }


def build_site_observability_snapshot(*, site_profile_path: Path | str | None = None) -> dict[str, Any]:
    """Build a read-only observability snapshot for one site."""

    profile = load_site_profile(site_profile_path) if site_profile_path else None
    validation_errors = validate_site_profile(profile) if profile else []
    deployment_mode = profile.deployment_mode if profile else "single-site"

    kafka_ok, kafka_probe_latency_ms = _timed_probe(probe_kafka)
    historian_ok, historian_probe_latency_ms = _timed_probe(probe_historian)
    ai_ok, ai_probe_latency_ms = _timed_probe(probe_ai_gateway)
    wal_g = get_walg_status()
    api_url = os.getenv("DATASTREAM_API_HEALTH_URL", "")
    api_ok: bool | None = None
    api_probe_latency_ms: float | None = None
    if api_url:
        api_ok, api_probe_latency_ms = _timed_probe(lambda: httpx.get(api_url, timeout=1.5).status_code < 500)

    signals = [
        ObservabilitySignal(
            name="broker_health",
            source="health_probes.probe_kafka",
            status="healthy" if kafka_ok else "degraded",
            value={"available": kafka_ok, "probe_latency_ms": kafka_probe_latency_ms},
        ),
        ObservabilitySignal(
            name="historian_health",
            source="health_probes.probe_historian",
            status="healthy" if historian_ok else "degraded",
            value={"available": historian_ok, "probe_latency_ms": historian_probe_latency_ms},
        ),
        ObservabilitySignal(
            name="ai_latency",
            source="health_probes.probe_ai_gateway",
            status="healthy" if ai_ok else "degraded",
            value={"available": ai_ok, "probe_latency_ms": ai_probe_latency_ms},
        ),
        ObservabilitySignal(
            name="backup_status",
            source="historian.backup.get_walg_status",
            status="healthy" if bool(wal_g.get("installed")) else "degraded",
            value=wal_g,
        ),
        ObservabilitySignal(
            name="ui_api_health",
            source="api_service.health_endpoint",
            status="unknown" if api_ok is None else "healthy" if api_ok else "degraded",
            value={"available": api_ok, "probe_latency_ms": api_probe_latency_ms},
        ),
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plane": "site-observability",
        "site_profile": profile.to_dict() if profile else None,
        "site_profile_validation": validation_errors,
        "deployment_mode": deployment_mode,
        "slo_targets": _slo_targets(deployment_mode),
        "signals": [signal.to_dict() for signal in signals],
        "slo_evaluation": _slo_evaluation(deployment_mode),
        "availability": {
            "broker_health": kafka_ok,
            "historian_health": historian_ok,
            "ai_gateway_health": ai_ok,
            "backup_tooling_ready": bool(wal_g.get("installed")),
            "api_health": api_ok,
        },
        "baseline_signals": [
            "ingest rate",
            "processing lag",
            "AI latency",
            "historian write latency",
            "backup status",
            "DLQ count",
            "broker health",
            "UI/API health",
        ],
        "signal_sources": {
            "ingest_rate": "prometheus or broker consumer metrics",
            "processing_lag": "processor lag metrics",
            "ai_latency": "ai gateway metrics",
            "historian_write_latency": "historian metrics",
            "backup_status": "wal-g and backup drill reports",
            "dlq_count": "dead-letter topic metrics",
            "broker_health": "health probe",
            "ui_api_health": "health endpoint",
        },
        "notes": [
            "This is a rollout-facing observability contract, not a replacement for Prometheus or Grafana.",
            "Use it to tell whether a site is healthy, degraded, or missing backup readiness.",
            "The actual continuous metrics still belong in the existing metrics stack.",
        ],
    }

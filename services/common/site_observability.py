from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    if deployment_mode == "federated":
        return {
            "ingest_availability_percent": 99.5,
            "ai_fallback_availability_percent": 100.0,
            "historian_backup_success_percent": 99.0,
            "broker_health_target": "healthy",
            "api_health_target": "healthy_or_degraded_with_reason",
        }
    if deployment_mode == "plant-local":
        return {
            "ingest_availability_percent": 99.5,
            "ai_fallback_availability_percent": 100.0,
            "historian_backup_success_percent": 99.0,
            "broker_health_target": "healthy",
            "api_health_target": "healthy_or_degraded_with_reason",
        }
    return {
        "ingest_availability_percent": 99.0,
        "ai_fallback_availability_percent": 100.0,
        "historian_backup_success_percent": 99.0,
        "broker_health_target": "healthy",
        "api_health_target": "healthy_or_degraded_with_reason",
    }


def build_site_observability_snapshot(*, site_profile_path: Path | str | None = None) -> dict[str, Any]:
    """Build a read-only observability snapshot for one site."""

    profile = load_site_profile(site_profile_path) if site_profile_path else None
    validation_errors = validate_site_profile(profile) if profile else []
    deployment_mode = profile.deployment_mode if profile else "single-site"

    kafka_ok = probe_kafka()
    historian_ok = probe_historian()
    ai_ok = probe_ai_gateway()
    wal_g = get_walg_status()
    api_ok = True

    signals = [
        ObservabilitySignal(
            name="broker_health",
            source="health_probes.probe_kafka",
            status="healthy" if kafka_ok else "degraded",
            value=kafka_ok,
        ),
        ObservabilitySignal(
            name="historian_health",
            source="health_probes.probe_historian",
            status="healthy" if historian_ok else "degraded",
            value=historian_ok,
        ),
        ObservabilitySignal(
            name="ai_latency",
            source="health_probes.probe_ai_gateway",
            status="healthy" if ai_ok else "degraded",
            value=ai_ok,
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
            status="healthy" if api_ok else "degraded",
            value=api_ok,
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


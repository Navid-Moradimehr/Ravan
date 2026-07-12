"""Lightweight, persisted threshold policies for industrial alarm evaluation.

The policy table is a metadata-plane store. It is intentionally small and
independent from telemetry rows: the historian answers what happened, while
this module answers which limits apply to a signal.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from services.assets.model import load_hierarchy


POLICY_MODES = {"above", "below", "outside_range", "between_range", "bad_quality"}
_CACHE_LOCK = Lock()
_POLICY_CACHE: tuple[float, dict[tuple[str, str, str], dict[str, Any]]] | None = None
_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _connection():
    from services.historian.client import get_connection

    return get_connection()


def ensure_policy_table() -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_threshold_policies (
                    site_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    unit TEXT,
                    mode TEXT NOT NULL DEFAULT 'outside_range',
                    warning_low DOUBLE PRECISION,
                    warning_high DOUBLE PRECISION,
                    critical_low DOUBLE PRECISION,
                    critical_high DOUBLE PRECISION,
                    deadband DOUBLE PRECISION NOT NULL DEFAULT 0,
                    on_delay_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    off_delay_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    source TEXT NOT NULL DEFAULT 'user',
                    version INTEGER NOT NULL DEFAULT 1,
                    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (site_id, asset_id, tag)
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS metadata_threshold_policies_site_idx "
                "ON metadata_threshold_policies (site_id, asset_id, tag)"
            )
        conn.commit()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"threshold value must be numeric: {value!r}") from exc


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    mode = str(policy.get("mode", "outside_range"))
    if mode not in POLICY_MODES:
        raise ValueError(f"unsupported threshold mode: {mode}")
    normalized = dict(policy)
    for field in ("warning_low", "warning_high", "critical_low", "critical_high"):
        normalized[field] = _number(policy.get(field))
    for field in ("deadband", "on_delay_seconds", "off_delay_seconds"):
        value = float(policy.get(field, 0) or 0)
        if value < 0:
            raise ValueError(f"{field} cannot be negative")
        normalized[field] = value
    if normalized["warning_low"] is not None and normalized["warning_high"] is not None and normalized["warning_low"] > normalized["warning_high"]:
        raise ValueError("warning_low must be less than or equal to warning_high")
    if normalized["critical_low"] is not None and normalized["critical_high"] is not None and normalized["critical_low"] > normalized["critical_high"]:
        raise ValueError("critical_low must be less than or equal to critical_high")
    normalized["enabled"] = bool(policy.get("enabled", True))
    normalized["source"] = str(policy.get("source", "user"))
    return normalized


def _manifest_policy(site_id: str, asset_id: str, tag: str, asset_config: str) -> dict[str, Any] | None:
    try:
        hierarchy = load_hierarchy(asset_config)
    except (OSError, KeyError, TypeError, ValueError):
        return None
    site = hierarchy.sites.get(site_id)
    if not site:
        return None
    for area in site.areas.values():
        for line in area.lines.values():
            for cell in line.cells.values():
                asset = cell.assets.get(asset_id)
                if not asset:
                    continue
                metadata = asset.tags.get(tag) or next((item for item in asset.tags.values() if item.name == tag), None)
                if not metadata:
                    continue
                return {
                    "site_id": site_id,
                    "asset_id": asset_id,
                    "tag": tag,
                    "unit": metadata.unit,
                    "mode": "outside_range",
                    "warning_low": metadata.warning_low,
                    "warning_high": metadata.warning_high,
                    "critical_low": metadata.critical_low,
                    "critical_high": metadata.critical_high,
                    "deadband": 0,
                    "on_delay_seconds": 0,
                    "off_delay_seconds": 0,
                    "enabled": True,
                    "source": "manifest",
                    "version": 0,
                    "configured": True,
                }
    return None


def _load_explicit_policies() -> dict[tuple[str, str, str], dict[str, Any]]:
    global _POLICY_CACHE
    ttl = max(0.0, float(os.getenv("THRESHOLD_POLICY_CACHE_SECONDS", "30")))
    now = time.monotonic()
    with _CACHE_LOCK:
        if _POLICY_CACHE and now - _POLICY_CACHE[0] < ttl:
            return _POLICY_CACHE[1]
    try:
        ensure_policy_table()
    except Exception:
        # The Python fallback and unit tests may run without the historian.
        # Manifest policies remain usable in that mode.
        return {}
    policies: dict[tuple[str, str, str], dict[str, Any]] = {}
    try:
        with _connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                """SELECT site_id, asset_id, tag, unit, mode, warning_low, warning_high,
                   critical_low, critical_high, deadband, on_delay_seconds,
                   off_delay_seconds, enabled, source, version, effective_from, updated_at
                   FROM metadata_threshold_policies"""
            )
                columns = [item[0] for item in cur.description]
                for row in cur.fetchall():
                    item = dict(zip(columns, row))
                    item["configured"] = True
                    policies[(str(item["site_id"]), str(item["asset_id"]), str(item["tag"]))] = item
    except Exception:
        return {}
    with _CACHE_LOCK:
        _POLICY_CACHE = (now, policies)
    return policies


def invalidate_policy_cache() -> None:
    global _POLICY_CACHE
    with _CACHE_LOCK:
        _POLICY_CACHE = None


def resolve_threshold_policy(
    site_id: str,
    asset_id: str,
    tag: str,
    *,
    asset_config: str = "config/assets.yaml",
) -> dict[str, Any]:
    explicit = _load_explicit_policies().get((site_id, asset_id, tag))
    if explicit:
        return explicit
    manifest = _manifest_policy(site_id, asset_id, tag, asset_config)
    if manifest:
        return manifest
    return {
        "site_id": site_id,
        "asset_id": asset_id,
        "tag": tag,
        "unit": "",
        "mode": "outside_range",
        "enabled": False,
        "source": "unconfigured",
        "version": 0,
        "configured": False,
    }


def list_threshold_policies(*, site_id: str | None = None) -> dict[str, Any]:
    policies = list(_load_explicit_policies().values())
    if site_id:
        policies = [item for item in policies if item.get("site_id") == site_id]
    return {
        "policies": policies,
        "source_precedence": ["user", "external_import", "manifest", "anomaly_score"],
        "contracts": {
            "user_policy_wins": True,
            "manifest_is_default_only": True,
            "runtime_does_not_query_historian": True,
        },
    }


def upsert_threshold_policy(policy: dict[str, Any]) -> dict[str, Any]:
    required = ("site_id", "asset_id", "tag")
    if any(not str(policy.get(field, "")).strip() for field in required):
        raise ValueError("site_id, asset_id, and tag are required")
    normalized = validate_policy(policy)
    ensure_policy_table()
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version FROM metadata_threshold_policies WHERE site_id=%s AND asset_id=%s AND tag=%s",
                (policy["site_id"], policy["asset_id"], policy["tag"]),
            )
            row = cur.fetchone()
            version = int(row[0]) + 1 if row else 1
            cur.execute(
                """INSERT INTO metadata_threshold_policies
                   (site_id, asset_id, tag, unit, mode, warning_low, warning_high,
                    critical_low, critical_high, deadband, on_delay_seconds,
                    off_delay_seconds, enabled, source, version, effective_from, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now())
                   ON CONFLICT (site_id, asset_id, tag) DO UPDATE SET
                    unit=EXCLUDED.unit, mode=EXCLUDED.mode,
                    warning_low=EXCLUDED.warning_low, warning_high=EXCLUDED.warning_high,
                    critical_low=EXCLUDED.critical_low, critical_high=EXCLUDED.critical_high,
                    deadband=EXCLUDED.deadband, on_delay_seconds=EXCLUDED.on_delay_seconds,
                    off_delay_seconds=EXCLUDED.off_delay_seconds, enabled=EXCLUDED.enabled,
                    source=EXCLUDED.source, version=EXCLUDED.version,
                    effective_from=EXCLUDED.effective_from, updated_at=now()""",
                (
                    policy["site_id"], policy["asset_id"], policy["tag"], policy.get("unit", ""),
                    normalized["mode"], normalized["warning_low"], normalized["warning_high"],
                    normalized["critical_low"], normalized["critical_high"], normalized["deadband"],
                    normalized["on_delay_seconds"], normalized["off_delay_seconds"],
                    normalized["enabled"], normalized["source"], version,
                ),
            )
        conn.commit()
    invalidate_policy_cache()
    return {**normalized, "site_id": policy["site_id"], "asset_id": policy["asset_id"], "tag": policy["tag"], "version": version, "configured": True}


def _outside(value: float, low: float | None, high: float | None) -> bool:
    return (low is not None and value <= low) or (high is not None and value >= high)


def evaluate_threshold(value: float, policy: dict[str, Any], *, quality: str = "good") -> dict[str, Any]:
    if not policy.get("enabled", False):
        return {"severity": "normal", "status": "unconfigured" if not policy.get("configured", False) else "disabled", "breached": False}
    if policy.get("mode") == "bad_quality":
        breached = str(quality).lower() not in {"good", "ok", "valid"}
        return {"severity": "critical" if breached else "normal", "status": "breached" if breached else "normal", "breached": breached}
    mode = policy.get("mode", "outside_range")
    warning_low, warning_high = policy.get("warning_low"), policy.get("warning_high")
    critical_low, critical_high = policy.get("critical_low"), policy.get("critical_high")
    if mode == "above":
        critical = critical_high is not None and value >= critical_high
        warning = warning_high is not None and value >= warning_high
    elif mode == "below":
        critical = critical_low is not None and value <= critical_low
        warning = warning_low is not None and value <= warning_low
    elif mode == "between_range":
        critical = critical_low is not None and critical_high is not None and critical_low <= value <= critical_high
        warning = warning_low is not None and warning_high is not None and warning_low <= value <= warning_high
    else:
        critical = _outside(value, critical_low, critical_high)
        warning = _outside(value, warning_low, warning_high)
    severity = "critical" if critical else "warning" if warning else "normal"
    return {"severity": severity, "status": "breached" if severity != "normal" else "normal", "breached": severity != "normal"}


def evaluate_threshold_runtime(
    key: str,
    value: float,
    policy: dict[str, Any],
    *,
    quality: str = "good",
    now: float | None = None,
) -> dict[str, Any]:
    """Apply optional deadband and transition delays in the local runtime.

    This is deliberately process-local for the Python fallback. A distributed
    Flink deployment must move the same state machine into keyed state before
    claiming cross-worker alarm lifecycle guarantees.
    """
    instant = evaluate_threshold(value, policy, quality=quality)
    previous = _RUNTIME_STATE.get(key, {"severity": "normal", "candidate": None, "since": None})
    previous_severity = str(previous.get("severity", "normal"))
    candidate = str(instant["severity"])
    deadband = float(policy.get("deadband", 0) or 0)
    if candidate == "normal" and previous_severity != "normal" and deadband:
        bounds = [policy.get("warning_low"), policy.get("warning_high")]
        near_boundary = any(bound is not None and abs(value - float(bound)) <= deadband for bound in bounds)
        if near_boundary:
            candidate = previous_severity
    delay = float(policy.get("off_delay_seconds" if candidate == "normal" else "on_delay_seconds", 0) or 0)
    clock = time.monotonic() if now is None else now
    if candidate != previous_severity and delay > 0:
        if previous.get("candidate") != candidate:
            previous = {"severity": previous_severity, "candidate": candidate, "since": clock}
        elif clock - float(previous.get("since") or clock) < delay:
            return {
                "severity": previous_severity,
                "status": "pending",
                "breached": previous_severity != "normal",
            }
    _RUNTIME_STATE[key] = {"severity": candidate, "candidate": None, "since": None}
    return {"severity": candidate, "status": "breached" if candidate != "normal" else "normal", "breached": candidate != "normal"}

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

from psycopg2.extras import Json

from services.assets.model import load_hierarchy
from services.common.threshold_policy_sync import (
    apply_threshold_snapshot,
    cache_policy as cache_threshold_policy,
    get_cached_policy,
    list_cached_policies,
    threshold_policy_sync_state,
)


POLICY_MODES = {"above", "below", "outside_range", "between_range", "bad_quality"}
_CACHE_LOCK = Lock()
_POLICY_CACHE: tuple[float, dict[tuple[str, str, str], dict[str, Any]]] | None = None
_MANIFEST_POLICY_CACHE: dict[str, tuple[float, dict[tuple[str, str, str], dict[str, Any]]]] = {}
_RUNTIME_STATE: dict[str, dict[str, Any]] = {}
_RESOLVED_POLICY_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}


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
    path = str(asset_config)
    try:
        modified_at = os.path.getmtime(path)
    except OSError:
        modified_at = -1.0

    # Asset manifests are metadata, not telemetry. Loading and walking the
    # hierarchy for every event made threshold resolution the dominant cost of
    # the keyed runtime path. Rebuild only when the source file changes.
    with _CACHE_LOCK:
        cached = _MANIFEST_POLICY_CACHE.get(path)
        if cached and cached[0] == modified_at:
            return cached[1].get((site_id, asset_id, tag))

    try:
        hierarchy = load_hierarchy(asset_config)
    except (OSError, KeyError, TypeError, ValueError):
        with _CACHE_LOCK:
            _MANIFEST_POLICY_CACHE[path] = (modified_at, {})
        return None
    policies: dict[tuple[str, str, str], dict[str, Any]] = {}
    for current_site_id, site in hierarchy.sites.items():
        for area in site.areas.values():
            for line in area.lines.values():
                for cell in line.cells.values():
                    for current_asset_id, asset in cell.assets.items():
                        for current_tag, metadata in asset.tags.items():
                            tag_name = str(getattr(metadata, "name", "") or current_tag)
                            policy = {
                                "site_id": current_site_id,
                                "asset_id": current_asset_id,
                                "tag": tag_name,
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
                            policies[(str(current_site_id), str(current_asset_id), tag_name)] = policy
                            policies[(str(current_site_id), str(current_asset_id), str(current_tag))] = policy

    with _CACHE_LOCK:
        _MANIFEST_POLICY_CACHE[path] = (modified_at, policies)
    return policies.get((site_id, asset_id, tag))


def _load_explicit_policies() -> dict[tuple[str, str, str], dict[str, Any]]:
    global _POLICY_CACHE
    cached = list_cached_policies()
    if cached:
        policies: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in cached:
            key = (str(item.get("site_id", "")), str(item.get("asset_id", "")), str(item.get("tag", "")))
            policies[key] = item
        with _CACHE_LOCK:
            _POLICY_CACHE = (time.monotonic(), policies)
        return policies
    now = time.monotonic()
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
    apply_threshold_snapshot(list(policies.values()), source="bootstrap", status="synced")
    return policies


def invalidate_policy_cache() -> None:
    global _POLICY_CACHE
    with _CACHE_LOCK:
        _POLICY_CACHE = None
        _MANIFEST_POLICY_CACHE.clear()
        _RESOLVED_POLICY_CACHE.clear()


def resolve_threshold_policy(
    site_id: str,
    asset_id: str,
    tag: str,
    *,
    asset_config: str = "config/assets.yaml",
) -> dict[str, Any]:
    lookup_key = (site_id, asset_id, tag)
    explicit = get_cached_policy(site_id, asset_id, tag)
    if explicit:
        return explicit
    explicit = _load_explicit_policies().get(lookup_key)
    if explicit:
        return explicit
    with _CACHE_LOCK:
        cached = _RESOLVED_POLICY_CACHE.get(lookup_key)
    if cached:
        return cached
    manifest = _manifest_policy(site_id, asset_id, tag, asset_config)
    if manifest:
        with _CACHE_LOCK:
            _RESOLVED_POLICY_CACHE[lookup_key] = manifest
        return manifest
    fallback = {
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
    with _CACHE_LOCK:
        _RESOLVED_POLICY_CACHE[lookup_key] = fallback
    return fallback


def list_threshold_policies(*, site_id: str | None = None) -> dict[str, Any]:
    policies = list(_load_explicit_policies().values())
    if site_id:
        policies = [item for item in policies if item.get("site_id") == site_id]
    sync_state = threshold_policy_sync_state()
    augmented = []
    for item in policies:
        copy = dict(item)
        copy["policy_key"] = f"{copy.get('site_id', '')}|{copy.get('asset_id', '')}|{copy.get('tag', '')}"
        copy["sync_status"] = copy.get("sync_status", sync_state.get("status", "synced"))
        augmented.append(copy)
    return {
        "policies": augmented,
        "source_precedence": ["user", "external_import", "manifest", "anomaly_score"],
        "contracts": {
            "user_policy_wins": True,
            "manifest_is_default_only": True,
            "runtime_does_not_query_historian": True,
        },
        "sync": sync_state,
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
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_threshold_policy_outbox (
                    outbox_id BIGSERIAL PRIMARY KEY,
                    policy_key TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    policy_version INTEGER NOT NULL,
                    payload JSONB NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    published_at TIMESTAMPTZ
                )
                """
            )
            payload = {
                **normalized,
                "site_id": policy["site_id"],
                "asset_id": policy["asset_id"],
                "tag": policy["tag"],
                "version": version,
                "configured": True,
            }
            cur.execute(
                """
                INSERT INTO metadata_threshold_policy_outbox (
                    policy_key, site_id, asset_id, tag, policy_version, payload, sync_status, attempts, updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,0,now())
                """,
                (
                    f"{policy['site_id']}|{policy['asset_id']}|{policy['tag']}",
                    policy["site_id"],
                    policy["asset_id"],
                    policy["tag"],
                    version,
                    Json(payload),
                    "pending",
                ),
            )
        conn.commit()
    cache_threshold_policy(payload)
    with _CACHE_LOCK:
        _RESOLVED_POLICY_CACHE[(policy["site_id"], policy["asset_id"], policy["tag"])] = payload
    return {
        **payload,
        "policy_key": f"{policy['site_id']}|{policy['asset_id']}|{policy['tag']}",
        "sync_status": "pending",
    }


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


def transition_threshold_state(
    previous_severity: str,
    candidate_since: float | None,
    value: float,
    policy: dict[str, Any],
    *,
    quality: str = "good",
    now: float | None = None,
) -> tuple[dict[str, Any], str | None, float | None]:
    """Evaluate one transition using caller-owned state.

    The returned state can be stored in Python memory or Flink keyed state.
    """
    instant = evaluate_threshold(value, policy, quality=quality)
    candidate = str(instant["severity"])
    deadband = float(policy.get("deadband", 0) or 0)
    if candidate == "normal" and previous_severity != "normal" and deadband:
        near_boundary = any(
            bound is not None and abs(value - float(bound)) <= deadband
            for bound in (policy.get("warning_low"), policy.get("warning_high"))
        )
        if near_boundary:
            candidate = previous_severity
    if candidate == previous_severity:
        return {"severity": previous_severity, "status": "breached" if previous_severity != "normal" else instant["status"], "breached": previous_severity != "normal"}, None, None
    delay = float(policy.get("off_delay_seconds" if candidate == "normal" else "on_delay_seconds", 0) or 0)
    clock = time.monotonic() if now is None else now
    since = clock if candidate_since is None else candidate_since
    if delay > 0 and clock - since < delay:
        return {"severity": previous_severity, "status": "pending", "breached": previous_severity != "normal"}, candidate, since
    return {"severity": candidate, "status": "breached" if candidate != "normal" else "normal", "breached": candidate != "normal"}, None, None


def evaluate_threshold_runtime(
    key: str,
    value: float,
    policy: dict[str, Any],
    *,
    quality: str = "good",
    now: float | None = None,
) -> dict[str, Any]:
    """Apply optional deadband and transition delays in the local runtime.

    This is the process-local adapter for the Python fallback. The distributed
    Flink adapter calls ``transition_threshold_state`` directly and stores its
    returned state in keyed state.
    """
    instant = evaluate_threshold(value, policy, quality=quality)
    previous = _RUNTIME_STATE.get(key, {"severity": "normal", "candidate": None, "since": None})
    previous_severity = str(previous.get("severity", "normal"))
    candidate = str(instant["severity"])
    deadband = float(policy.get("deadband", 0) or 0)
    clock = time.monotonic() if now is None else now
    result, next_candidate, next_since = transition_threshold_state(
        previous_severity,
        previous.get("since") if previous.get("candidate") == candidate else None,
        value,
        policy,
        quality=quality,
        now=clock,
    )
    _RUNTIME_STATE[key] = {"severity": result["severity"], "candidate": next_candidate, "since": next_since}
    return result

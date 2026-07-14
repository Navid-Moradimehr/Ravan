"""Governed AI reporting policy and durable job helpers.

This is deliberately a logical control-plane module, not a new service. Database
imports are lazy so CLI and unit-test users can inspect policy contracts without a
running historian.
"""
from __future__ import annotations

import uuid
import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


MIN_INTERVAL_SECONDS = 600
MAX_INTERVAL_SECONDS = 86400


class AIReportingPolicy(BaseModel):
    enabled: bool = True
    scheduled_enabled: bool = True
    scheduled_interval_seconds: int = Field(default=3600, ge=MIN_INTERVAL_SECONDS, le=MAX_INTERVAL_SECONDS)
    anomaly_enabled: bool = False
    anomaly_duration_seconds: int = Field(default=20, ge=20, le=600)
    anomaly_severity: str = "critical"
    anomaly_min_samples: int = Field(default=3, ge=3, le=1000)
    anomaly_rearm_seconds: int = Field(default=60, ge=0, le=86400)
    anomaly_cooldown_seconds: int = Field(default=1800, ge=0, le=86400)
    exclude_replay: bool = True
    max_evidence_events: int = Field(default=100, ge=1, le=1000)

    @field_validator("anomaly_severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"critical", "warning", "any"}:
            raise ValueError("anomaly_severity must be critical, warning, or any")
        return value


def default_policy() -> AIReportingPolicy:
    return AIReportingPolicy()


class SustainedAnomalyTracker:
    """Bounded per-stream tracker for one report per sustained incident."""

    def __init__(self, max_streams: int = 10000) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._max_streams = max_streams

    def update(self, event: dict[str, Any], policy: AIReportingPolicy, *, now: float | None = None) -> list[dict[str, Any]] | None:
        if not policy.anomaly_enabled or (policy.exclude_replay and _is_replay(event)):
            return None
        severity = str(event.get("severity") or "normal").lower()
        qualifies = policy.anomaly_severity == "any" or severity == policy.anomaly_severity or (policy.anomaly_severity == "warning" and severity == "critical")
        key = ":".join(str(event.get(field) or "unknown") for field in ("site_id", "asset_id", "tag"))
        now = time.monotonic() if now is None else now
        state = self._states.get(key)
        if not qualifies:
            if state and state.get("reported") and severity == "normal" and now - float(state["last_seen"]) >= policy.anomaly_rearm_seconds:
                self._states.pop(key, None)
            elif state and not state.get("reported"):
                self._states.pop(key, None)
            return None
        if state is None:
            if len(self._states) >= self._max_streams:
                self._states.pop(next(iter(self._states)))
            state = {"started": now, "last_seen": now, "count": 0, "reported": False, "evidence": [], "last_report": 0.0}
            self._states[key] = state
        state["last_seen"] = now
        state["count"] += 1
        state["evidence"] = (state["evidence"] + [event])[-policy.max_evidence_events :]
        if state["reported"] or state["count"] < policy.anomaly_min_samples or now - float(state["started"]) < policy.anomaly_duration_seconds:
            return None
        if state["last_report"] and now - float(state["last_report"]) < policy.anomaly_cooldown_seconds:
            return None
        state["reported"] = True
        state["last_report"] = now
        return list(state["evidence"])


def _is_replay(event: dict[str, Any]) -> bool:
    return bool(event.get("replay") or event.get("is_replay") or event.get("replay_source") or str(event.get("source_protocol", "")).lower() == "dataset")


def _db():
    from services.historian.client import get_connection

    return get_connection


def ensure_ai_reporting_tables() -> None:
    with _db()() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_ai_reporting_policy (
                    policy_id TEXT PRIMARY KEY,
                    site_id TEXT NOT NULL UNIQUE,
                    policy JSONB NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS ai_report_jobs (
                    job_id UUID PRIMARY KEY,
                    site_id TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    trigger_reason TEXT NOT NULL,
                    window_start TIMESTAMPTZ,
                    window_end TIMESTAMPTZ,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    policy_snapshot JSONB NOT NULL,
                    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                    result JSONB,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                CREATE INDEX IF NOT EXISTS ai_report_jobs_status_idx
                    ON ai_report_jobs (status, next_attempt_at);
                CREATE UNIQUE INDEX IF NOT EXISTS ai_report_jobs_window_uniq
                    ON ai_report_jobs (site_id, report_type, trigger_reason, window_start, window_end);
                """
            )
        conn.commit()


def get_policy(site_id: str = "*") -> AIReportingPolicy:
    try:
        ensure_ai_reporting_tables()
        with _db()() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT policy FROM metadata_ai_reporting_policy WHERE site_id IN (%s, '*') ORDER BY CASE WHEN site_id = %s THEN 0 ELSE 1 END LIMIT 1", (site_id, site_id))
                row = cur.fetchone()
        if row:
            return AIReportingPolicy.model_validate(row[0])
    except Exception:
        # The gateway must remain compatible with a pre-migration database.
        pass
    return default_policy()


def save_policy(policy: AIReportingPolicy, site_id: str = "*") -> dict[str, Any]:
    from psycopg2.extras import Json

    ensure_ai_reporting_tables()
    with _db()() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO metadata_ai_reporting_policy (policy_id, site_id, policy)
                VALUES (%s, %s, %s)
                ON CONFLICT (site_id) DO UPDATE SET policy = EXCLUDED.policy,
                    version = metadata_ai_reporting_policy.version + 1,
                    updated_at = now()
                RETURNING policy_id, site_id, policy, version, updated_at
                """,
                (str(uuid.uuid4()), site_id, Json(policy.model_dump(mode="json"))),
            )
            row = cur.fetchone()
        conn.commit()
    return {"policy_id": row[0], "site_id": row[1], "policy": row[2], "version": row[3], "updated_at": row[4]}


def create_report_job(
    *,
    site_id: str,
    report_type: str,
    trigger_reason: str,
    window_start: datetime | None,
    window_end: datetime | None,
    policy: AIReportingPolicy,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from psycopg2.extras import Json

    ensure_ai_reporting_tables()
    job_id = str(uuid.uuid4())
    evidence = (evidence or [])[: policy.max_evidence_events]
    with _db()() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_report_jobs
                    (job_id, site_id, report_type, trigger_reason, window_start,
                     window_end, policy_snapshot, evidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (site_id, report_type, trigger_reason, window_start, window_end)
                DO UPDATE SET updated_at = now()
                RETURNING job_id, site_id, report_type, trigger_reason, window_start,
                          window_end, status, attempts, policy_snapshot, evidence,
                          created_at, updated_at
                """,
                (job_id, site_id, report_type, trigger_reason, window_start, window_end, Json(policy.model_dump(mode="json")), Json(evidence)),
            )
            row = cur.fetchone()
        conn.commit()
    columns = ["job_id", "site_id", "report_type", "trigger_reason", "window_start", "window_end", "status", "attempts", "policy_snapshot", "evidence", "created_at", "updated_at"]
    return dict(zip(columns, row))


def complete_report_job(job_id: str, result: dict[str, Any] | None = None) -> None:
    ensure_ai_reporting_tables()
    from psycopg2.extras import Json
    with _db()() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE ai_report_jobs SET status = 'completed', result = %s, updated_at = now() WHERE job_id = %s", (Json(result or {}), job_id))
        conn.commit()


def fail_report_job(job_id: str, error: str, retry_after_seconds: int = 60) -> None:
    ensure_ai_reporting_tables()
    with _db()() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE ai_report_jobs SET status = 'pending', attempts = attempts + 1,
                         last_error = %s, next_attempt_at = now() + (%s * interval '1 second'), updated_at = now()
                         WHERE job_id = %s""", (error[:2000], max(1, retry_after_seconds), job_id))
        conn.commit()


def list_report_jobs(*, site_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_ai_reporting_tables()
    limit = max(1, min(limit, 200))
    with _db()() as conn:
        with conn.cursor() as cur:
            if site_id:
                cur.execute("SELECT job_id, site_id, report_type, trigger_reason, window_start, window_end, status, attempts, last_error, created_at, updated_at FROM ai_report_jobs WHERE site_id = %s ORDER BY created_at DESC LIMIT %s", (site_id, limit))
            else:
                cur.execute("SELECT job_id, site_id, report_type, trigger_reason, window_start, window_end, status, attempts, last_error, created_at, updated_at FROM ai_report_jobs ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
    keys = ["job_id", "site_id", "report_type", "trigger_reason", "window_start", "window_end", "status", "attempts", "last_error", "created_at", "updated_at"]
    return [dict(zip(keys, row)) for row in rows]


def reporting_status(site_id: str = "*") -> dict[str, Any]:
    policy = get_policy(site_id)
    return {
        "site_id": site_id,
        "policy": policy.model_dump(mode="json"),
        "defaults": default_policy().model_dump(mode="json"),
        "source": "database_or_default",
        "min_interval_seconds": MIN_INTERVAL_SECONDS,
        "max_interval_seconds": MAX_INTERVAL_SECONDS,
    }

"""Governed AI reporting policy and durable job helpers.

This is deliberately a logical control-plane module, not a new service. Database
imports are lazy so CLI and unit-test users can inspect policy contracts without a
running historian.
"""
from __future__ import annotations

import uuid
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

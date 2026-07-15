"""Durable metadata for model-data manifests and optional build jobs."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.historian.client import get_connection


def ensure_dataset_tables() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_training_manifests (
                    dataset_id TEXT NOT NULL,
                    manifest_version INTEGER NOT NULL,
                    manifest JSONB NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (dataset_id, manifest_version)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_build_jobs (
                    job_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    manifest_version INTEGER NOT NULL,
                    manifest_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    error TEXT NOT NULL DEFAULT '',
                    heartbeat_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_build_artifacts (
                    job_id TEXT NOT NULL REFERENCES dataset_build_jobs(job_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size_bytes BIGINT NOT NULL DEFAULT 0,
                    PRIMARY KEY (job_id, name)
                )
                """
            )
        conn.commit()


def save_manifest(manifest: dict[str, Any], content_hash: str) -> dict[str, Any]:
    from psycopg2.extras import Json

    dataset_id = str(manifest["dataset_id"])
    version = int(manifest.get("manifest_version", 1))
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO metadata_training_manifests (dataset_id, manifest_version, manifest, content_hash)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (dataset_id, manifest_version) DO UPDATE SET manifest=EXCLUDED.manifest, content_hash=EXCLUDED.content_hash""",
                (dataset_id, version, Json(manifest), content_hash),
            )
        conn.commit()
    return {"dataset_id": dataset_id, "manifest_version": version, "content_hash": content_hash}


def list_manifests(dataset_id: str | None = None) -> list[dict[str, Any]]:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dataset_id, manifest_version, manifest, content_hash, created_at::text FROM metadata_training_manifests WHERE (%s IS NULL OR dataset_id=%s) ORDER BY dataset_id, manifest_version DESC",
                (dataset_id, dataset_id),
            )
            return [
                {"dataset_id": row[0], "manifest_version": row[1], "manifest": row[2], "content_hash": row[3], "created_at": row[4]}
                for row in cur.fetchall()
            ]


def create_build_job(dataset_id: str, manifest_version: int, manifest_path: str, output_dir: str) -> dict[str, Any]:
    ensure_dataset_tables()
    job_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dataset_build_jobs (job_id, dataset_id, manifest_version, manifest_path, output_dir) VALUES (%s,%s,%s,%s,%s)",
                (job_id, dataset_id, manifest_version, manifest_path, output_dir),
            )
        conn.commit()
    return {"job_id": job_id, "dataset_id": dataset_id, "status": "queued", "output_dir": output_dir}


def claim_build_job(worker_id: str) -> dict[str, Any] | None:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT job_id, dataset_id, manifest_version, manifest_path, output_dir
                   FROM dataset_build_jobs WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"""
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return None
            now = datetime.now(timezone.utc)
            cur.execute(
                "UPDATE dataset_build_jobs SET status='running', heartbeat_at=%s, started_at=%s, error='' WHERE job_id=%s",
                (now, now, row[0]),
            )
        conn.commit()
    return {"job_id": row[0], "dataset_id": row[1], "manifest_version": row[2], "manifest_path": row[3], "output_dir": row[4], "worker_id": worker_id}


def finish_build_job(job_id: str, status: str, error: str = "", output_dir: str = "") -> None:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE dataset_build_jobs SET status=%s, error=%s, finished_at=now(), heartbeat_at=now() WHERE job_id=%s", (status, error, job_id))
            if status == "succeeded" and output_dir:
                for path in Path(output_dir).iterdir():
                    if path.is_file():
                        cur.execute("INSERT INTO dataset_build_artifacts (job_id, name, path, size_bytes) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING", (job_id, path.name, str(path), path.stat().st_size))
        conn.commit()


def list_build_jobs() -> list[dict[str, Any]]:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT job_id, dataset_id, manifest_version, status, error, output_dir, created_at::text, finished_at::text FROM dataset_build_jobs ORDER BY created_at DESC")
            return [{"job_id": r[0], "dataset_id": r[1], "manifest_version": r[2], "status": r[3], "error": r[4], "output_dir": r[5], "created_at": r[6], "finished_at": r[7]} for r in cur.fetchall()]


def get_build_job(job_id: str) -> dict[str, Any] | None:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT job_id, dataset_id, manifest_version, status, error, output_dir, created_at::text, finished_at::text FROM dataset_build_jobs WHERE job_id=%s", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {"job_id": row[0], "dataset_id": row[1], "manifest_version": row[2], "status": row[3], "error": row[4], "output_dir": row[5], "created_at": row[6], "finished_at": row[7]}


def cancel_build_job(job_id: str) -> bool:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE dataset_build_jobs SET status='cancelled', finished_at=now() WHERE job_id=%s AND status='queued'", (job_id,))
            changed = cur.rowcount > 0
        conn.commit()
    return changed


def get_build_artifacts(job_id: str) -> list[dict[str, Any]]:
    ensure_dataset_tables()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, path, size_bytes FROM dataset_build_artifacts WHERE job_id=%s ORDER BY name", (job_id,))
            return [{"name": r[0], "path": r[1], "size_bytes": r[2]} for r in cur.fetchall()]

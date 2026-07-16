"""Durable idempotency ledger for HTTP Push ingress.

The API keeps the event body out of this table. Only the bounded key and the
small response are persisted, allowing retries across API restarts and
replicas without turning the historian into a request cache.
"""
from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any

import psycopg2

from services.historian.client import _connection_string

TABLE = "http_push_idempotency"
_TABLE_LOCK = Lock()
_TABLE_READY = False


class IdempotencyUnavailable(RuntimeError):
    """Raised when durable deduplication cannot be consulted safely."""


def _connect():
    dsn = os.getenv("DATASTREAM_HTTP_PUSH_IDEMPOTENCY_DSN") or _connection_string()
    return psycopg2.connect(dsn)


def ensure_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    with _TABLE_LOCK:
        if _TABLE_READY:
            return
        connection = _connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    idempotency_key TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL DEFAULT '',
                    response JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS {TABLE}_created_idx ON {TABLE} (created_at DESC)"
                    )
            _TABLE_READY = True
        finally:
            connection.close()


def claim(key: str, event_id: str = "") -> dict[str, Any] | None:
    """Atomically claim a key; return a prior response for duplicates."""
    try:
        ensure_table()
        connection = _connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""INSERT INTO {TABLE} (idempotency_key, event_id)
                        VALUES (%s, %s) ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING idempotency_key""",
                        (key, event_id),
                    )
                    if cursor.fetchone():
                        return None
                    cursor.execute(
                        f"SELECT response, event_id FROM {TABLE} WHERE idempotency_key = %s",
                        (key,),
                    )
                    row = cursor.fetchone()
                    response = row[0] if row else None
                    prior_event_id = str(row[1]) if row and row[1] else event_id
                    if isinstance(response, dict):
                        return {**response, "status": "duplicate"}
                    return {"status": "duplicate", "event_id": prior_event_id}
        finally:
            connection.close()
    except Exception as exc:
        raise IdempotencyUnavailable(f"durable HTTP Push idempotency unavailable: {exc}") from exc


def complete(key: str, response: dict[str, Any]) -> None:
    try:
        connection = _connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                    f"UPDATE {TABLE} SET response = %s::jsonb, updated_at = now() WHERE idempotency_key = %s",
                    (json.dumps(response), key),
                    )
        finally:
            connection.close()
    except Exception as exc:
        raise IdempotencyUnavailable(f"durable HTTP Push response persistence failed: {exc}") from exc


def release(key: str) -> None:
    try:
        connection = _connect()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(f"DELETE FROM {TABLE} WHERE idempotency_key = %s", (key,))
        finally:
            connection.close()
    except Exception as exc:
        raise IdempotencyUnavailable(f"durable HTTP Push claim release failed: {exc}") from exc

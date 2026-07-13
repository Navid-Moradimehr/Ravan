"""Real dependency probes for the health endpoint.

Each probe is intentionally lightweight and bounded by a short timeout so a slow
or dead dependency cannot hang ``/health``. Probes return ``True`` when the
dependency responds, ``False`` otherwise; they never raise.
"""

from __future__ import annotations

import logging
import os
import socket

import psycopg2

logger = logging.getLogger(__name__)

_PROBE_TIMEOUT_SECONDS = 1.5


def probe_kafka() -> bool:
    """Probe Kafka by opening a TCP connection to the first broker."""
    brokers = os.getenv("KAFKA_BROKERS", "localhost:19092")
    first = brokers.split(",")[0].strip()
    if ":" in first:
        host, _, port = first.rpartition(":")
    else:
        host, port = first, "9092"
    try:
        with socket.create_connection((host, int(port)), timeout=_PROBE_TIMEOUT_SECONDS):
            return True
    except Exception as exc:
        logger.debug("kafka probe failed: %s", exc)
        return False


def probe_historian() -> bool:
    """Probe the historian by running a cheap ``SELECT 1``.

    Uses a short-lived connection instead of the application pool so a pool
    exhausted by ingestion cannot make the health endpoint wait indefinitely.
    """
    try:
        from services.historian import client as historian_client
        dsn = historian_client._connection_string()
    except Exception:
        return False
    connection = None
    try:
        connection = psycopg2.connect(
            dsn,
            connect_timeout=max(1, int(_PROBE_TIMEOUT_SECONDS)),
            options=f"-c statement_timeout={int(_PROBE_TIMEOUT_SECONDS * 1000)}",
        )
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as exc:
        logger.debug("historian probe failed: %s", exc)
        return False
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def probe_ai_gateway() -> bool:
    """Probe the AI gateway over HTTP."""
    import httpx

    base = os.getenv("DATASTREAM_AI_BASE", "http://localhost:8080")
    try:
        resp = httpx.get(f"{base}/health", timeout=_PROBE_TIMEOUT_SECONDS)
        return resp.status_code < 500
    except Exception as exc:
        logger.debug("ai-gateway probe failed: %s", exc)
        return False

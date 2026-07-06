"""Real dependency probes for the health endpoint.

Each probe is intentionally lightweight and bounded by a short timeout so a slow
or dead dependency cannot hang ``/health``. Probes return ``True`` when the
dependency responds, ``False`` otherwise; they never raise.
"""

from __future__ import annotations

import logging
import os
import socket

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

    Imports the client module (not the name) so tests can patch
    ``historian_client.get_connection`` and the probe observes the patch.
    """
    try:
        from services.historian import client as historian_client
    except Exception:
        return False
    try:
        with historian_client.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception as exc:
        logger.debug("historian probe failed: %s", exc)
        return False


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

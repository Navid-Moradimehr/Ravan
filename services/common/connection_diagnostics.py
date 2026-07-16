"""Bounded, non-ingesting connection diagnostics."""
from __future__ import annotations

import socket
from urllib.parse import urlparse
from typing import Any

import httpx

from services.common.connection_registry import METADATA_ONLY_PROTOCOLS, RUNTIME_PROTOCOLS, SourceConnection


def _host_port(connection: SourceConnection) -> tuple[str, int] | None:
    parsed = urlparse(connection.endpoint)
    if parsed.hostname and parsed.port:
        return parsed.hostname, parsed.port
    if connection.source_protocol == "modbus" and ":" in connection.endpoint:
        host, port = connection.endpoint.removeprefix("modbus://").rsplit(":", 1)
        return host, int(port)
    return None


def _rest_probe(connection: SourceConnection, timeout_seconds: float) -> dict[str, Any]:
    from services.edge_ingest.rest_support import resolved_auth

    options = connection.config
    url = str(options.get("url") or connection.endpoint).strip()
    method = str(options.get("method", "GET")).upper()
    headers, params, basic, cert = resolved_auth(options, connection.credential_refs)
    headers.setdefault("Accept", "application/json")
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False, cert=cert) as client:
            response = client.request(method, url, headers=headers, params=params, auth=basic, json=options.get("body"))
        return {
            "network_test": "reachable" if response.status_code < 500 else "unhealthy",
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
        }
    except httpx.TimeoutException:
        return {"network_test": "timeout"}
    except (httpx.HTTPError, OSError, ValueError) as exc:
        return {"network_test": "unreachable", "network_error": str(exc)}


def run_connection_test(connection: SourceConnection, timeout_seconds: float = 3.0) -> dict[str, object]:
    """Test configuration and TCP reachability without ingesting or persisting data."""
    draft_errors = connection.validate_draft()
    activation_errors = connection.activation_errors()
    result: dict[str, object] = {
        "connection_id": connection.connection_id,
        "valid": not draft_errors,
        "activation_ready": not activation_errors,
        "configuration_errors": draft_errors,
        "activation_errors": activation_errors,
        "network_test": "not_run",
        "endpoint": connection.endpoint,
    }
    if draft_errors:
        return result
    if connection.source_protocol in METADATA_ONLY_PROTOCOLS:
        result["network_test"] = "not_required"
        return result
    if connection.source_protocol == "http_push":
        result["network_test"] = "not_required"
        result["activation_endpoint"] = f"/api/v1/connections/{connection.connection_id}/events"
        return result
    if connection.source_protocol == "rest":
        result.update(_rest_probe(connection, timeout_seconds))
        return result
    if connection.source_protocol not in RUNTIME_PROTOCOLS:
        result["network_test"] = "unsupported_protocol"
        result["network_error"] = f"{connection.source_protocol} is not started by the edge runtime"
        return result
    if connection.source_protocol == "modbus_rtu":
        result["network_test"] = "serial_endpoint_deferred"
        return result
    host_port = _host_port(connection)
    if host_port is None:
        result["network_test"] = "unsupported_endpoint_format"
        return result
    host, port = host_port
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            result["network_test"] = "reachable"
    except socket.timeout:
        result["network_test"] = "timeout"
    except OSError as exc:
        result["network_test"] = "unreachable"
        result["network_error"] = str(exc)
    return result

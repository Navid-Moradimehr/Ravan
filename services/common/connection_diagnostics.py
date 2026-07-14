"""Bounded, non-ingesting connection diagnostics."""
from __future__ import annotations

import socket
from urllib.parse import urlparse

from services.common.connection_registry import METADATA_ONLY_PROTOCOLS, RUNTIME_PROTOCOLS, SourceConnection


def _host_port(connection: SourceConnection) -> tuple[str, int] | None:
    parsed = urlparse(connection.endpoint)
    if parsed.hostname and parsed.port:
        return parsed.hostname, parsed.port
    if connection.source_protocol == "modbus" and ":" in connection.endpoint:
        host, port = connection.endpoint.removeprefix("modbus://").rsplit(":", 1)
        return host, int(port)
    return None


def run_connection_test(connection: SourceConnection, timeout_seconds: float = 3.0) -> dict[str, object]:
    """Test configuration and TCP reachability without ingesting or persisting data."""
    errors = connection.validate()
    result: dict[str, object] = {
        "connection_id": connection.connection_id,
        "valid": not errors,
        "configuration_errors": errors,
        "network_test": "not_run",
        "endpoint": connection.endpoint,
    }
    if errors:
        return result
    if connection.source_protocol in METADATA_ONLY_PROTOCOLS:
        result["network_test"] = "not_required"
        return result
    if connection.source_protocol not in RUNTIME_PROTOCOLS:
        result["network_test"] = "unsupported_protocol"
        result["network_error"] = f"{connection.source_protocol} is not started by the edge runtime"
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

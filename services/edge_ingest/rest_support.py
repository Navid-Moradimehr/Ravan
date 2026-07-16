"""Small, bounded helpers shared by REST pull and HTTP diagnostics.

The module deliberately contains request construction and JSON extraction only;
publishing, retries, lifecycle, and source health remain owned by the caller.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.edge_ingest.credentials import CredentialResolutionError, resolve_credentials, resolve_reference


def deep_get(value: Any, path: str, default: Any = None) -> Any:
    """Read a dotted JSON path, accepting either a mapping or list index."""
    current = value
    for part in [item for item in str(path or "").strip(".").split(".") if item]:
        if isinstance(current, Mapping):
            if part not in current:
                return default
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return default
            current = current[index]
        else:
            return default
    return current


def records_from_response(payload: Any, records_path: str = "") -> list[dict[str, Any]]:
    value = deep_get(payload, records_path, None) if records_path else payload
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def resolved_auth(config: dict[str, Any], credential_refs: dict[str, str] | None) -> tuple[dict[str, str], dict[str, str], tuple[str, str] | None, str | tuple[str, str] | None]:
    """Build non-secret request auth material at the connector boundary."""
    auth = config.get("auth", {}) if isinstance(config.get("auth", {}), dict) else {}
    auth_type = str(auth.get("type", "none")).lower()
    references = dict(credential_refs or {})
    for key in ("username_ref", "password_ref", "token_ref", "key_ref", "client_id_ref", "client_secret_ref", "client_cert_ref", "client_key_ref"):
        if auth.get(key) and key not in references:
            references[key] = str(auth[key])
    resolved = resolve_credentials(references)
    headers = {str(key): str(value) for key, value in (config.get("headers", {}) or {}).items()}
    params = {str(key): str(value) for key, value in (config.get("query_params", {}) or {}).items()}
    basic: tuple[str, str] | None = None
    cert: str | tuple[str, str] | None = None
    if auth_type == "basic":
        basic = (resolved.get("username_ref") or resolved.get("username", ""), resolved.get("password_ref") or resolved.get("password", ""))
    elif auth_type == "bearer":
        token = resolved.get("token_ref") or resolved.get("token", "")
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        key = resolved.get("key_ref") or resolved.get("api_key", "")
        name = str(auth.get("name", "X-API-Key"))
        if str(auth.get("location", "header")).lower() == "query":
            params[name] = key
        else:
            headers[name] = key
    elif auth_type == "mtls":
        cert = (resolved.get("client_cert_ref", ""), resolved.get("client_key_ref", ""))
    return headers, params, basic, cert


def event_from_record(
    record: dict[str, Any],
    *,
    field_paths: dict[str, str],
    connection_id: str,
    site_id: str,
    source_id: str,
    protocol: str = "rest",
) -> dict[str, Any]:
    """Map one external record to the canonical ingress shape."""
    event: dict[str, Any] = {
        "source_protocol": protocol,
        "source_connection_id": connection_id,
        "source_id": deep_get(record, field_paths.get("source_id", ""), source_id) or source_id,
        "asset_id": deep_get(record, field_paths.get("asset_id", ""), ""),
        "tag": deep_get(record, field_paths.get("tag", ""), ""),
        "value": deep_get(record, field_paths.get("value", ""), None),
        "quality": deep_get(record, field_paths.get("quality", ""), "good") or "good",
        "unit": deep_get(record, field_paths.get("unit", ""), "") or "",
        "site": deep_get(record, field_paths.get("site", ""), site_id) or site_id,
        "line": deep_get(record, field_paths.get("line", ""), "") or "",
        "ts_source": deep_get(record, field_paths.get("ts_source", ""), None),
    }
    event_id = deep_get(record, field_paths.get("event_id", ""), None)
    if event_id:
        event["event_id"] = str(event_id)
    return event

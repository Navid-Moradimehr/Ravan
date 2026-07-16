"""Bounded REST pull connector.

REST is an edge source, not a historian shortcut: responses are converted to
canonical events and pass through the same publisher, mapping, validation,
Kafka, DLQ, and fan-out path as PLC protocols.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx

from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects
from services.edge_ingest.rest_support import deep_get, event_from_record, records_from_response, resolved_auth
from services.edge_ingest.credentials import resolve_credentials
from services.edge_ingest.settings import Settings, SourceRuntime
from services.edge_ingest.source_health import mark_mapping_result, mark_source, mark_source_success

logger = logging.getLogger(__name__)


def _deterministic_event_id(connection_id: str, event: dict[str, Any]) -> str:
    identity = "|".join(str(event.get(key, "")) for key in ("source_id", "asset_id", "tag", "ts_source", "value"))
    return hashlib.sha256(f"{connection_id}|{identity}".encode("utf-8")).hexdigest()


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


async def _apply_oauth2(client: httpx.AsyncClient, options: dict[str, Any], headers: dict[str, str], refs: dict[str, str] | None) -> None:
    auth = options.get("auth", {}) if isinstance(options.get("auth", {}), dict) else {}
    if str(auth.get("type", "none")).lower() != "oauth2_client_credentials":
        return
    references = {
        "client_id": str(auth.get("client_id_ref", "")),
        "client_secret": str(auth.get("client_secret_ref", "")),
    }
    references.update({key: value for key, value in (refs or {}).items() if key in {"client_id", "client_secret"}})
    credentials = resolve_credentials({key: value for key, value in references.items() if value})
    token_url = str(auth.get("token_url", ""))
    data = {"grant_type": "client_credentials", "client_id": credentials.get("client_id", ""), "client_secret": credentials.get("client_secret", "")}
    scopes = auth.get("scopes", [])
    if scopes:
        data["scope"] = " ".join(str(item) for item in scopes)
    response = await client.post(token_url, data=data)
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("OAuth2 token response did not contain access_token")
    headers["Authorization"] = f"Bearer {token}"


async def _request_with_retries(client: httpx.AsyncClient, method: str, url: str, *, headers: dict[str, str], params: dict[str, str], auth: tuple[str, str] | None, json_body: Any, retries: int) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.request(method, url, headers=headers, params=params, auth=auth, json=json_body)
            if response.status_code not in {408, 425, 429} and response.status_code < 500:
                return response
            last = RuntimeError(f"REST response status {response.status_code}")
        except (httpx.HTTPError, OSError) as exc:
            last = exc
        if attempt < retries:
            await asyncio.sleep(min(10.0, 0.5 * (2**attempt)))
    raise last or RuntimeError("REST request failed")


async def run_rest(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    source = source or next(item for item in settings.source_connections() if item.source_protocol == "rest")
    options = source.options
    url = str(options.get("url") or source.endpoint).strip()
    method = str(options.get("method", "GET")).upper()
    interval = max(1.0, min(86400.0, float(options.get("poll_interval_seconds", settings.poll_seconds))))
    timeout = max(1.0, min(300.0, float(options.get("timeout_seconds", 15))))
    retries = _bounded_int(options.get("max_retries", 3), 3, 0, 8)
    response_config = options.get("response", {}) if isinstance(options.get("response", {}), dict) else {}
    field_paths = response_config.get("field_paths", {}) if isinstance(response_config.get("field_paths", {}), dict) else {}
    records_path = str(response_config.get("records_path", ""))
    pagination = options.get("pagination", {}) if isinstance(options.get("pagination", {}), dict) else {}
    page_mode = str(pagination.get("mode", "none")).lower()
    max_pages = _bounded_int(pagination.get("max_pages", 1 if page_mode == "none" else 10), 10, 1, 100)
    max_records = _bounded_int(options.get("max_records_per_poll", 10000), 10000, 1, 100000)
    state: dict[str, str] = {}
    try:
        headers, params, basic, cert = resolved_auth(options, source.credential_refs)
    except Exception as exc:
        mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(exc))
        adapter_errors.labels(protocol="rest").inc()
        return
    headers.update({"Accept": "application/json", "User-Agent": "local-stream-engine-rest/1"})
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    body = options.get("body")

    client_kwargs: dict[str, Any] = {"timeout": timeout, "follow_redirects": False}
    if cert:
        client_kwargs["cert"] = cert
    async with httpx.AsyncClient(**client_kwargs) as client:
        try:
            await _apply_oauth2(client, options, headers, source.credential_refs)
        except Exception as exc:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", f"OAuth2 authentication failed: {exc}")
            adapter_errors.labels(protocol="rest").inc()
            return
        while not stop_event.is_set():
            started = time.monotonic()
            try:
                next_cursor = ""
                total_records = 0
                for page in range(max_pages):
                    request_params = dict(params)
                    if page_mode == "page":
                        request_params[str(pagination.get("page_param", "page"))] = str(page + 1)
                        request_params[str(pagination.get("size_param", "limit"))] = str(pagination.get("page_size", 100))
                    elif page_mode == "offset":
                        request_params[str(pagination.get("offset_param", "offset"))] = str(page * int(pagination.get("page_size", 100)))
                        request_params[str(pagination.get("size_param", "limit"))] = str(pagination.get("page_size", 100))
                    elif page_mode == "cursor" and next_cursor:
                        request_params[str(pagination.get("cursor_param", "cursor"))] = next_cursor
                    response = await _request_with_retries(client, method, url, headers=headers, params=request_params, auth=basic, json_body=body, retries=retries)
                    if response.status_code == 304:
                        mark_source_success(source.connection_id, source.source_protocol, source.site_id)
                        break
                    response.raise_for_status()
                    if response.headers.get("ETag"):
                        state["etag"] = response.headers["ETag"]
                        headers["If-None-Match"] = state["etag"]
                    payload = response.json()
                    records = records_from_response(payload, records_path)
                    for record in records[: max(0, max_records - total_records)]:
                        event = event_from_record(record, field_paths=field_paths, connection_id=source.connection_id, site_id=source.site_id, source_id=source.source_id or url)
                        event["event_id"] = _deterministic_event_id(source.connection_id, event)
                        event["ts_source"] = event.get("ts_source") or utc_now()
                        # Preserve the source record on the raw topic for
                        # replay and diagnosis; canonical validation drops
                        # this transport envelope before normalized processing.
                        event["raw_record"] = record
                        mapped, matched, source_field = source.map_event_with_status(event)
                        publisher.publish_event(mapped)
                        mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                        total_records += 1
                    if total_records >= max_records or page_mode == "none" or not records:
                        break
                    if page_mode == "cursor":
                        next_cursor = str(deep_get(payload, str(pagination.get("next_cursor_path", "")), "") or "")
                        if not next_cursor:
                            break
                mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
                mark_source_success(source.connection_id, source.source_protocol, source.site_id)
            except (httpx.HTTPError, ValueError, OSError, RuntimeError) as exc:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(exc))
                adapter_errors.labels(protocol="rest").inc()
                adapter_reconnects.labels(protocol="rest").inc()
            elapsed = time.monotonic() - started
            if not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=max(0.1, interval - elapsed))
                except asyncio.TimeoutError:
                    pass

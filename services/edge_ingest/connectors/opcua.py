from __future__ import annotations

import asyncio
import os
from typing import Any

from asyncua import Client

from services.common.device_compat import unit_for_tag
from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects
from services.edge_ingest.source_health import mark_source, mark_source_success
from services.edge_ingest.source_health import mark_mapping_result
from services.edge_ingest.settings import Settings, SourceRuntime
from services.edge_ingest.credentials import CredentialResolutionError, resolve_credentials
from services.edge_ingest.opcua_security import validate_security_material


def opcua_quality(status: Any) -> str:
    """Map an OPC UA StatusCode without discarding uncertain/bad quality."""
    if status is None:
        return "good"
    try:
        if status.is_good():
            return "good"
        if status.is_bad():
            return "bad"
    except (AttributeError, TypeError):
        pass
    text = str(status).lower()
    if "bad" in text:
        return "bad"
    if "uncertain" in text:
        return "uncertain"
    return "good"


async def read_opcua_sample(node: Any) -> tuple[Any, str, str]:
    """Read the server value, quality, and source timestamp when available."""
    read_data_value = getattr(node, "read_data_value", None)
    if not callable(read_data_value):
        return await node.read_value(), "good", utc_now()
    data_value = await read_data_value()
    variant = getattr(data_value, "Value", None)
    value = getattr(variant, "Value", variant)
    source_timestamp = getattr(data_value, "SourceTimestamp", None)
    timestamp = source_timestamp.isoformat() if source_timestamp is not None else utc_now()
    return value, opcua_quality(getattr(data_value, "StatusCode", None)), timestamp


async def run_opcua(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    source = source or settings.source_connections()[0]
    endpoint = source.endpoint or settings.opcua_endpoint
    nodes = tuple(source.options.get("nodes") or settings.opcua_nodes)
    while not stop_event.is_set():
        try:
            opcua_cert = os.getenv("OPCUA_CERTIFICATE", "")
            opcua_key = os.getenv("OPCUA_PRIVATE_KEY", "")
            credentials = resolve_credentials(source.credential_refs)
            opcua_cert = credentials.get("certificate", opcua_cert)
            opcua_key = credentials.get("private_key", opcua_key)
            client_kwargs: dict[str, Any] = {}
            if opcua_cert and opcua_key:
                client_kwargs["certificate"] = opcua_cert
                client_kwargs["private_key"] = opcua_key
            async with Client(endpoint, **client_kwargs) as client:
                security = source.options.get("security", {}) if isinstance(source.options.get("security", {}), dict) else {}
                security_string = str(credentials.get("security_string", security.get("security_string", ""))).strip()
                try:
                    validate_security_material(credentials, security)
                except ValueError as exc:
                    raise CredentialResolutionError(str(exc)) from exc
                if security_string:
                    await client.set_security_string(security_string)
                username = credentials.get("username", "")
                password = credentials.get("password", "")
                if username:
                    client.set_user(username)
                if password:
                    client.set_password(password)
                mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
                while not stop_event.is_set():
                    for node_id in nodes:
                        value, quality, source_timestamp = await read_opcua_sample(client.get_node(node_id))
                        asset_id, tag = node_id.split(";s=", 1)[1].split(".", 1)
                        payload = {
                            "source_protocol": "opcua",
                            "source_id": source.source_id or node_id,
                            "asset_id": asset_id,
                            "tag": tag,
                            "value": value,
                            "quality": quality,
                            "unit": unit_for_tag(tag),
                            "site": source.site_id,
                            "ts_source": source_timestamp,
                        }
                        mapped, matched, source_field = source.map_event_with_status(payload)
                        publisher.publish_event(mapped)
                        mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                        mark_source_success(source.connection_id, source.source_protocol, source.site_id)
                    await asyncio.sleep(settings.poll_seconds)
        except CredentialResolutionError as exc:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(exc))
            adapter_errors.labels(protocol="opcua").inc()
            await asyncio.sleep(3)
        except Exception:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "OPC UA connection or read failed")
            adapter_errors.labels(protocol="opcua").inc()
            adapter_reconnects.labels(protocol="opcua").inc()
            await asyncio.sleep(3)

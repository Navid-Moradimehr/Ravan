from __future__ import annotations

import asyncio
import os
from typing import Any

from asyncua import Client

from services.common.device_compat import unit_for_tag
from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects
from services.edge_ingest.source_health import mark_source, mark_source_success
from services.edge_ingest.settings import Settings, SourceRuntime


async def run_opcua(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    source = source or settings.source_connections()[0]
    endpoint = source.endpoint or settings.opcua_endpoint
    nodes = tuple(source.options.get("nodes") or settings.opcua_nodes)
    while not stop_event.is_set():
        try:
            opcua_cert = os.getenv("OPCUA_CERTIFICATE", "")
            opcua_key = os.getenv("OPCUA_PRIVATE_KEY", "")
            client_kwargs: dict[str, Any] = {}
            if opcua_cert and opcua_key:
                client_kwargs["certificate"] = opcua_cert
                client_kwargs["private_key"] = opcua_key
            async with Client(endpoint, **client_kwargs) as client:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
                while not stop_event.is_set():
                    for node_id in nodes:
                        value = await client.get_node(node_id).read_value()
                        asset_id, tag = node_id.split(";s=", 1)[1].split(".", 1)
                        publisher.publish_event(source.map_event(
                            {
                                "source_protocol": "opcua",
                                "source_id": source.source_id or node_id,
                                "asset_id": asset_id,
                                "tag": tag,
                                "value": value,
                                "quality": "good",
                                "unit": unit_for_tag(tag),
                                "site": source.site_id,
                                "ts_source": utc_now(),
                            }
                        ))
                        mark_source_success(source.connection_id, source.source_protocol, source.site_id)
                    await asyncio.sleep(settings.poll_seconds)
        except Exception:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "OPC UA connection or read failed")
            adapter_errors.labels(protocol="opcua").inc()
            adapter_reconnects.labels(protocol="opcua").inc()
            await asyncio.sleep(3)

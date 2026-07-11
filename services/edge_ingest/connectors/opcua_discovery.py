from __future__ import annotations

import asyncio
import os

from services.edge_ingest.model import utc_now
from services.edge_ingest.opcua_discovery import OPCUADiscoveryClient
from services.edge_ingest.publisher import EdgePublisher, adapter_errors
from services.edge_ingest.source_health import mark_mapping_result
from services.edge_ingest.settings import Settings, SourceRuntime
from services.common.device_compat import unit_for_tag
from services.edge_ingest.source_health import mark_source, mark_source_success


async def run_opcua_discovery(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    if source is None and "opcua_discovery" not in settings.enabled_protocols:
        return
    source = source or settings.source_connections()[0]
    endpoint = source.endpoint or os.getenv("OPCUA_DISCOVERY_ENDPOINT", "opc.tcp://localhost:4840")
    nodes = [n.strip() for n in source.options.get("nodes", []) if n.strip()]
    if not nodes:
        nodes = [n.strip() for n in os.getenv("OPCUA_DISCOVERY_NODES", "").split(",") if n.strip()]
    client = OPCUADiscoveryClient(endpoint)
    while not stop_event.is_set():
        try:
            connected = await client.connect()
            if not connected:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "OPC UA discovery connection failed")
                await asyncio.sleep(5)
                continue
            for node_id in nodes:
                value = await client.read_node_value(node_id)
                if value is not None:
                    payload = {
                        "source_protocol": "opcua",
                        "source_id": source.source_id or node_id,
                        "asset_id": node_id.split(".")[0] if "." in node_id else "unknown",
                        "tag": node_id.split(".")[-1] if "." in node_id else node_id,
                        "value": float(value),
                        "quality": "good",
                        "unit": unit_for_tag(node_id),
                        "site": source.site_id,
                        "ts_source": utc_now(),
                    }
                    mapped, matched, source_field = source.map_event_with_status(payload)
                    publisher.publish_event(mapped)
                    mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                    mark_source_success(source.connection_id, source.source_protocol, source.site_id)
            await asyncio.sleep(settings.poll_seconds)
        except Exception:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "OPC UA discovery failed")
            adapter_errors.labels(protocol="opcua_discovery").inc()
            await asyncio.sleep(5)

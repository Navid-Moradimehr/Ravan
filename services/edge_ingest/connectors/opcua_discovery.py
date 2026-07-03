from __future__ import annotations

import asyncio
import os

from services.edge_ingest.model import utc_now
from services.edge_ingest.opcua_discovery import OPCUADiscoveryClient
from services.edge_ingest.publisher import EdgePublisher, adapter_errors
from services.edge_ingest.settings import Settings
from services.common.device_compat import unit_for_tag


async def run_opcua_discovery(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    if "opcua_discovery" not in settings.enabled_protocols:
        return
    endpoint = os.getenv("OPCUA_DISCOVERY_ENDPOINT", "opc.tcp://localhost:4840")
    nodes = [n.strip() for n in os.getenv("OPCUA_DISCOVERY_NODES", "").split(",") if n.strip()]
    client = OPCUADiscoveryClient(endpoint)
    while not stop_event.is_set():
        try:
            connected = await client.connect()
            if not connected:
                await asyncio.sleep(5)
                continue
            for node_id in nodes:
                value = await client.read_node_value(node_id)
                if value is not None:
                    publisher.publish_event(
                        {
                            "source_protocol": "opcua",
                            "source_id": node_id,
                            "asset_id": node_id.split(".")[0] if "." in node_id else "unknown",
                            "tag": node_id.split(".")[-1] if "." in node_id else node_id,
                            "value": float(value),
                            "quality": "good",
                            "unit": unit_for_tag(node_id),
                            "ts_source": utc_now(),
                        }
                    )
            await asyncio.sleep(settings.poll_seconds)
        except Exception:
            adapter_errors.labels(protocol="opcua_discovery").inc()
            await asyncio.sleep(5)

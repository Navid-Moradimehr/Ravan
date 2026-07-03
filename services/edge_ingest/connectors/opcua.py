from __future__ import annotations

import asyncio
import os
from typing import Any

from asyncua import Client

from services.common.device_compat import unit_for_tag
from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects
from services.edge_ingest.settings import Settings


async def run_opcua(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            opcua_cert = os.getenv("OPCUA_CERTIFICATE", "")
            opcua_key = os.getenv("OPCUA_PRIVATE_KEY", "")
            client_kwargs: dict[str, Any] = {}
            if opcua_cert and opcua_key:
                client_kwargs["certificate"] = opcua_cert
                client_kwargs["private_key"] = opcua_key
            async with Client(settings.opcua_endpoint, **client_kwargs) as client:
                while not stop_event.is_set():
                    for node_id in settings.opcua_nodes:
                        value = await client.get_node(node_id).read_value()
                        asset_id, tag = node_id.split(";s=", 1)[1].split(".", 1)
                        publisher.publish_event(
                            {
                                "source_protocol": "opcua",
                                "source_id": node_id,
                                "asset_id": asset_id,
                                "tag": tag,
                                "value": value,
                                "quality": "good",
                                "unit": unit_for_tag(tag),
                                "ts_source": utc_now(),
                            }
                        )
                    await asyncio.sleep(settings.poll_seconds)
        except Exception:
            adapter_errors.labels(protocol="opcua").inc()
            adapter_reconnects.labels(protocol="opcua").inc()
            await asyncio.sleep(3)

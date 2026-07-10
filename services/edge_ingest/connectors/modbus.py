from __future__ import annotations

import asyncio
import os
import ssl

from pymodbus.client import ModbusTcpClient

from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects
from services.edge_ingest.settings import Settings, SourceRuntime


async def run_modbus(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    source = source or settings.source_connections()[0]
    endpoint = source.endpoint.removeprefix("modbus://") if source.endpoint else ""
    endpoint_host, _, endpoint_port = endpoint.partition(":")
    host = endpoint_host or settings.modbus_host
    port = int(endpoint_port or settings.modbus_port)
    register_map = [(0, "Temperature", "c"), (1, "Vibration", "mm/s"), (2, "Pressure", "bar")]
    while not stop_event.is_set():
        modbus_tls = os.getenv("MODBUS_TLS", "false").lower() == "true"
        modbus_ca = os.getenv("MODBUS_CA_CERT", "")
        sslctx: ssl.SSLContext | None = None
        if modbus_tls and modbus_ca:
            sslctx = ssl.create_default_context(cafile=modbus_ca)
        client = ModbusTcpClient(
            host,
            port=port,
            sslctx=sslctx,
        )
        try:
            if not client.connect():
                raise ConnectionError("modbus connect failed")
            while not stop_event.is_set():
                result = client.read_holding_registers(address=0, count=3, slave=1)
                if result.isError():
                    raise RuntimeError(str(result))
                for address, tag, unit in register_map:
                    scale = 10 if tag != "Vibration" else 100
                    publisher.publish_event(source.map_event(
                        {
                            "source_protocol": "modbus",
                            "source_id": source.source_id or f"{host}:{port}/hr/{address}",
                            "asset_id": str(source.options.get("asset_id", "Pump-03")),
                            "tag": tag,
                            "value": result.registers[address] / scale,
                            "quality": "good",
                            "unit": unit,
                            "site": source.site_id,
                            "ts_source": utc_now(),
                        }
                    ))
                await asyncio.sleep(settings.poll_seconds)
        except Exception:
            adapter_errors.labels(protocol="modbus").inc()
            adapter_reconnects.labels(protocol="modbus").inc()
            await asyncio.sleep(3)
        finally:
            client.close()

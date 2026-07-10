from __future__ import annotations

import asyncio
import os

from services.edge_ingest.modbus_rtu_client import ModbusRTUClient
from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors
from services.edge_ingest.settings import Settings, SourceRuntime
from services.edge_ingest.source_health import mark_source, mark_source_success


async def run_modbus_rtu(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    if "modbus_rtu" not in settings.enabled_protocols:
        return
    source = source or settings.source_connections()[0]
    options = source.options
    port = str(options.get("port") or os.getenv("MODBUS_RTU_PORT", "/dev/ttyUSB0"))
    baudrate = int(options.get("baudrate") or os.getenv("MODBUS_RTU_BAUDRATE", "9600"))
    slave_id = int(options.get("slave_id") or os.getenv("MODBUS_RTU_SLAVE_ID", "1"))
    register_text = str(options.get("registers") or os.getenv("MODBUS_RTU_REGISTERS", "0:1"))
    registers = [(int(a.split(":")[0]), int(a.split(":")[1])) for a in register_text.split(",") if ":" in a]
    client = ModbusRTUClient(port=port, baudrate=baudrate, slave_id=slave_id)
    while not stop_event.is_set():
        try:
            if not client._client or not client._client.connected:
                client.connect()
            mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
            for addr, count in registers:
                values = client.read_holding_registers(addr, count)
                if values:
                    for i, val in enumerate(values):
                        publisher.publish_event(source.map_event(
                            {
                                "source_protocol": "modbus_rtu",
                                "source_id": source.source_id or f"{port}:{slave_id}:hr/{addr+i}",
                                "asset_id": str(options.get("asset_id", f"RTU-{slave_id}")),
                                "tag": f"register_{addr+i}",
                                "value": float(val),
                                "quality": "good",
                                "unit": "",
                                "site": source.site_id,
                                "ts_source": utc_now(),
                            }
                        ))
                        mark_source_success(source.connection_id, source.source_protocol, source.site_id)
            await asyncio.sleep(settings.poll_seconds)
        except Exception:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "Modbus RTU connection or read failed")
            adapter_errors.labels(protocol="modbus_rtu").inc()
            client.disconnect()
            await asyncio.sleep(5)

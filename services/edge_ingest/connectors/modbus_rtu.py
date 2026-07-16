from __future__ import annotations

import asyncio
import os

from services.edge_ingest.modbus_rtu_client import ModbusRTUClient
from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors
from services.edge_ingest.source_health import mark_mapping_result
from services.edge_ingest.settings import Settings, SourceRuntime
from services.edge_ingest.source_health import mark_source, mark_source_success
from services.edge_ingest.connectors.modbus_registers import decode_registers, normalize_register, register_count


async def run_modbus_rtu(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    if source is None and "modbus_rtu" not in settings.enabled_protocols:
        return
    source = source or settings.source_connections()[0]
    options = source.options
    port = str(options.get("port") or os.getenv("MODBUS_RTU_PORT", "/dev/ttyUSB0"))
    baudrate = int(options.get("baudrate") or os.getenv("MODBUS_RTU_BAUDRATE", "9600"))
    slave_id = int(options.get("slave_id") or os.getenv("MODBUS_RTU_SLAVE_ID", "1"))
    configured_registers = options.get("registers")
    if isinstance(configured_registers, list):
        registers = [normalize_register(item) for item in configured_registers]
    else:
        register_text = str(configured_registers or os.getenv("MODBUS_RTU_REGISTERS", "0:1"))
        registers = [{"address": int(a.split(":")[0]), "count": int(a.split(":")[1]), "tag": f"register_{a.split(':')[0]}", "unit": "", "scale": 1.0, "offset": 0.0, "unit_id": slave_id, "data_type": "uint16", "byte_order": "big", "word_order": "big"} for a in register_text.split(",") if ":" in a]
    client = ModbusRTUClient(port=port, baudrate=baudrate, slave_id=slave_id)
    while not stop_event.is_set():
        try:
            if not client._client or not client._client.connected:
                client.connect()
            mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
            for register in registers:
                addr = register["address"]
                count = register.get("count", register_count(register["data_type"]))
                values = client.read_holding_registers(addr, count)
                if values:
                    value = decode_registers(values[:count], register["data_type"], register["byte_order"], register["word_order"])
                    if register["data_type"] != "bool":
                        value = value * register["scale"] + register["offset"]
                    for i, val in enumerate(values) if register["data_type"] == "uint16" and count == 1 else [(0, value)]:
                        payload = {
                            "source_protocol": "modbus_rtu",
                            "source_id": source.source_id or f"{port}:{slave_id}:hr/{addr+i}",
                            "asset_id": str(options.get("asset_id", f"RTU-{slave_id}")),
                            "tag": register["tag"] if count != 1 or register["tag"] else f"register_{addr+i}",
                            "value": val if register["data_type"] == "bool" else float(val),
                            "quality": "good",
                            "unit": "",
                            "site": source.site_id,
                            "ts_source": utc_now(),
                        }
                        mapped, matched, source_field = source.map_event_with_status(payload)
                        publisher.publish_event(mapped)
                        mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                        mark_source_success(source.connection_id, source.source_protocol, source.site_id)
            await asyncio.sleep(settings.poll_seconds)
        except Exception:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "Modbus RTU connection or read failed")
            adapter_errors.labels(protocol="modbus_rtu").inc()
            client.disconnect()
            await asyncio.sleep(5)

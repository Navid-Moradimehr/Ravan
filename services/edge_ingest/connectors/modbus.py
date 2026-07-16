from __future__ import annotations

import asyncio
import os
import ssl

from pymodbus.client import ModbusTcpClient, ModbusTlsClient

from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects
from services.edge_ingest.source_health import mark_mapping_result
from services.edge_ingest.settings import Settings, SourceRuntime
from services.edge_ingest.source_health import mark_source, mark_source_success


async def run_modbus(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    source = source or settings.source_connections()[0]
    endpoint = source.endpoint.removeprefix("modbus://") if source.endpoint else ""
    endpoint_host, _, endpoint_port = endpoint.partition(":")
    host = endpoint_host or settings.modbus_host
    port = int(endpoint_port or settings.modbus_port)
    configured_registers = source.options.get("registers") or []
    if configured_registers:
        register_map = [
            (int(item["address"]), str(item.get("tag", f"register_{item['address']}")), str(item.get("unit", "")), float(item.get("scale", 1.0)), float(item.get("offset", 0.0)), int(item.get("unit_id", item.get("slave_id", 1))))
            for item in configured_registers
        ]
    elif not source.registry_managed:
        register_map = [(0, "Temperature", "c", 0.1, 0.0, 1), (1, "Vibration", "mm/s", 0.01, 0.0, 1), (2, "Pressure", "bar", 0.1, 0.0, 1)]
    else:
        mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "registry source has no explicit register map")
        return
    while not stop_event.is_set():
        modbus_tls = os.getenv("MODBUS_TLS", "false").lower() == "true"
        modbus_ca = os.getenv("MODBUS_CA_CERT", "")
        sslctx: ssl.SSLContext | None = None
        if modbus_tls and modbus_ca:
            sslctx = ssl.create_default_context(cafile=modbus_ca)
        if sslctx is not None:
            client = ModbusTlsClient(host, port=port, sslctx=sslctx)
        else:
            # ModbusTcpClient does not accept an sslctx keyword. Keep the
            # plain TCP path separate from the TLS client so default sources
            # work with current pymodbus releases.
            client = ModbusTcpClient(host, port=port)
        try:
            if not client.connect():
                raise ConnectionError("modbus connect failed")
            mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
            while not stop_event.is_set():
                for address, tag, unit, scale, offset, slave_id in register_map:
                    result = client.read_holding_registers(address=address, count=1, slave=slave_id)
                    if result.isError():
                        raise RuntimeError(str(result))
                    payload = {
                        "source_protocol": "modbus",
                        "source_id": source.source_id or f"{host}:{port}/hr/{address}",
                        "asset_id": str(source.options.get("asset_id", "Pump-03")),
                        "tag": tag,
                        "value": result.registers[0] * scale + offset,
                        "quality": "good",
                        "unit": unit,
                        "site": source.site_id,
                        "ts_source": utc_now(),
                    }
                    mapped, matched, source_field = source.map_event_with_status(payload)
                    publisher.publish_event(mapped)
                    mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                    mark_source_success(source.connection_id, source.source_protocol, source.site_id)
                await asyncio.sleep(settings.poll_seconds)
        except Exception:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", "Modbus connection or read failed")
            adapter_errors.labels(protocol="modbus").inc()
            adapter_reconnects.labels(protocol="modbus").inc()
            await asyncio.sleep(3)
        finally:
            client.close()

from __future__ import annotations

import asyncio
try:
    import serial.tools.list_ports
except ImportError:
    serial = None
import json
import os
import signal
import time
from dataclasses import dataclass
from typing import Any

from asyncua import Client
from confluent_kafka import Producer
from paho.mqtt import client as mqtt
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from pymodbus.client import ModbusTcpClient

from services.edge_ingest.model import IndustrialEvent, validate_event, to_json_bytes, utc_now
from services.assets.model import load_hierarchy
from services.historian.client import insert_industrial_event, insert_industrial_events
from services.common.normalize import to_legacy_iot_event
from services.common.device_compat import unit_for_tag
from services.edge_ingest.modbus_rtu_client import ModbusRTUClient, scan_modbus_rtu_devices
from services.edge_ingest.opcua_discovery import OPCUADiscoveryClient
from services.common.stream_scope import stream_partition_key


events_total = Counter("edge_ingest_events_total", "Validated industrial events", ["protocol"])
dlq_total = Counter("edge_ingest_dlq_total", "Invalid industrial events", ["protocol"])
adapter_errors = Counter("edge_ingest_adapter_errors_total", "Adapter errors", ["protocol"])
adapter_reconnects = Counter("edge_ingest_reconnects_total", "Adapter reconnect attempts", ["protocol"])
last_success_epoch = Gauge("edge_ingest_last_success_epoch", "Last successful ingest timestamp", ["protocol"])
ingest_latency = Histogram("edge_ingest_latency_seconds", "Source-to-ingest latency", ["protocol"])


@dataclass(frozen=True)
class Settings:
    brokers: str = os.getenv("REDPANDA_BROKERS", "localhost:19092")
    normalized_topic: str = os.getenv("INDUSTRIAL_NORMALIZED_TOPIC", "industrial.normalized")
    raw_topic: str = os.getenv("INDUSTRIAL_RAW_TOPIC", "industrial.raw")
    legacy_topic: str = os.getenv("IOT_TOPIC", "iot.raw")
    dlq_topic: str = os.getenv("INDUSTRIAL_DLQ_TOPIC", "industrial.dlq")
    enabled_protocols: tuple[str, ...] = tuple(
        item.strip().lower()
        for item in os.getenv("EDGE_PROTOCOLS", "mqtt,opcua,modbus").split(",")
        if item.strip()
    )
    metrics_port: int = int(os.getenv("EDGE_METRICS_PORT", "8090"))
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_topic: str = os.getenv("MQTT_TOPIC", "factory/+/+/+")
    opcua_endpoint: str = os.getenv("OPCUA_ENDPOINT", "opc.tcp://localhost:4840/freeopcua/server/")
    opcua_nodes: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv(
            "OPCUA_NODES",
            "ns=2;s=Pump-01.Temperature,ns=2;s=Pump-01.Vibration,ns=2;s=Pump-01.Pressure",
        ).split(",")
        if item.strip()
    )
    modbus_host: str = os.getenv("MODBUS_HOST", "localhost")
    modbus_port: int = int(os.getenv("MODBUS_PORT", "5020"))
    poll_seconds: float = float(os.getenv("EDGE_POLL_SECONDS", "1"))


class EdgePublisher:
    def __init__(self, settings: Settings, batch_size: int = 256, flush_interval_ms: float = 1000.0):
        self.settings = settings
        self.producer = Producer({
            "bootstrap.servers": settings.brokers,
            "client.id": "edge-ingest",
            "enable.idempotence": True,
            "acks": "all",
            "retries": 10,
            "batch.size": 16384,
            "linger.ms": 10,
            "compression.type": "lz4",
            "queue.buffering.max.messages": 100000,
        })
        self._batch_size = batch_size
        self._flush_interval_ms = flush_interval_ms
        self._buffer: list[tuple[str, bytes, bytes]] = []
        self._historian_buffer: list[dict[str, Any]] = []
        self._last_flush = time.time()

    def publish_raw(self, protocol: str, source_id: str, payload: dict[str, Any]) -> None:
        self.producer.produce(
            self.settings.raw_topic,
            key=f"{protocol}:{source_id}".encode("utf-8"),
            value=to_json_bytes(payload),
        )

    def publish_event(self, payload: dict[str, Any]) -> None:
        protocol = str(payload.get("source_protocol", "unknown"))
        source_id = str(payload.get("source_id", "unknown"))
        self.publish_raw(protocol, source_id, payload)
        event, dlq = validate_event(payload)
        if dlq:
            self._buffer.append((self.settings.dlq_topic, source_id.encode("utf-8"), to_json_bytes(dlq)))
            dlq_total.labels(protocol=protocol).inc()
        else:
            assert event is not None
            key = stream_partition_key(event)
            self._buffer.append((self.settings.normalized_topic, key, to_json_bytes(event)))
            self._buffer.append((self.settings.legacy_topic, key, to_json_bytes(to_legacy_iot_event(event))))
            self._historian_buffer.append(event.model_dump(mode="json"))
            events_total.labels(protocol=event.source_protocol).inc()
            last_success_epoch.labels(protocol=event.source_protocol).set(time.time())
            observe_latency(event)
        
        self._maybe_flush()

    def _maybe_flush(self) -> None:
        now = time.time()
        elapsed_ms = (now - self._last_flush) * 1000
        if len(self._buffer) >= self._batch_size or elapsed_ms >= self._flush_interval_ms:
            self._flush_buffer()
        if len(self._historian_buffer) >= self._batch_size or elapsed_ms >= self._flush_interval_ms:
            self._flush_historian_buffer()

    def _flush_buffer(self) -> None:
        for topic, key, value in self._buffer:
            self.producer.produce(topic, key=key, value=value)
        self._buffer.clear()
        self.producer.poll(0)
        self._last_flush = time.time()

    def _flush_historian_buffer(self) -> None:
        if not self._historian_buffer:
            return

        batch = self._historian_buffer[:]
        self._historian_buffer.clear()
        try:
            insert_industrial_events(batch)
        except Exception as exc:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("historian industrial-event batch write failed: %s", exc)
            for event in batch:
                try:
                    insert_industrial_event(event)
                except Exception as inner_exc:  # pragma: no cover - logged failure path
                    logger.warning("historian industrial-event fallback write failed: %s", inner_exc)

    def flush(self) -> None:
        self._flush_historian_buffer()
        self._flush_buffer()
        self.producer.flush(10)


def observe_latency(event: IndustrialEvent) -> None:
    try:
        source_epoch = time.mktime(time.strptime(event.ts_source[:19], "%Y-%m-%dT%H:%M:%S"))
        ingest_latency.labels(protocol=event.source_protocol).observe(max(time.time() - source_epoch, 0))
    except Exception:
        return


async def run_mqtt(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    def on_connect(client: mqtt.Client, _userdata: object, _flags: dict[str, Any], reason_code: int, _properties: object = None) -> None:
        if reason_code == 0:
            client.subscribe(settings.mqtt_topic)
        else:
            adapter_errors.labels(protocol="mqtt").inc()

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            publisher.publish_event(payload)
        except Exception as exc:
            dlq_total.labels(protocol="mqtt").inc()
            publisher.publish_event(
                {
                    "source_protocol": "mqtt",
                    "source_id": message.topic,
                    "asset_id": "",
                    "tag": "",
                    "value": str(message.payload),
                    "quality": "bad",
                    "ts_source": utc_now(),
                    "error": str(exc),
                }
            )

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="edge-ingest-mqtt")
    client.on_connect = on_connect
    client.on_message = on_message
    # TLS for MQTT (optional)
    mqtt_ca_cert = os.getenv("MQTT_CA_CERT", "")
    mqtt_certfile = os.getenv("MQTT_CERTFILE", "")
    mqtt_keyfile = os.getenv("MQTT_KEYFILE", "")
    if mqtt_ca_cert:
        client.tls_set(
            ca_certs=mqtt_ca_cert,
            certfile=mqtt_certfile or None,
            keyfile=mqtt_keyfile or None,
        )
    while not stop_event.is_set():
        try:
            client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
            client.loop_start()
            await stop_event.wait()
        except Exception:
            adapter_errors.labels(protocol="mqtt").inc()
            adapter_reconnects.labels(protocol="mqtt").inc()
            await asyncio.sleep(3)
        finally:
            client.loop_stop()
            client.disconnect()


async def run_opcua(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            # TLS for OPC UA (optional)
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


async def run_modbus(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    register_map = [(0, "Temperature", "c"), (1, "Vibration", "mm/s"), (2, "Pressure", "bar")]
    while not stop_event.is_set():
        # TLS for Modbus TCP (optional)
        modbus_tls = os.getenv("MODBUS_TLS", "false").lower() == "true"
        modbus_ca = os.getenv("MODBUS_CA_CERT", "")
        import ssl
        sslctx: ssl.SSLContext | None = None
        if modbus_tls and modbus_ca:
            sslctx = ssl.create_default_context(cafile=modbus_ca)
        client = ModbusTcpClient(
            settings.modbus_host,
            port=settings.modbus_port,
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
                    publisher.publish_event(
                        {
                            "source_protocol": "modbus",
                            "source_id": f"{settings.modbus_host}:{settings.modbus_port}/hr/{address}",
                            "asset_id": "Pump-03",
                            "tag": tag,
                            "value": result.registers[address] / scale,
                            "quality": "good",
                            "unit": unit,
                            "ts_source": utc_now(),
                        }
                    )
                await asyncio.sleep(settings.poll_seconds)
        except Exception:
            adapter_errors.labels(protocol="modbus").inc()
            adapter_reconnects.labels(protocol="modbus").inc()
            await asyncio.sleep(3)
        finally:
            client.close()


async def run_modbus_rtu(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    """Modbus RTU serial ingestion loop."""
    if "modbus_rtu" not in settings.enabled_protocols:
        return
    port = os.getenv("MODBUS_RTU_PORT", "/dev/ttyUSB0")
    baudrate = int(os.getenv("MODBUS_RTU_BAUDRATE", "9600"))
    slave_id = int(os.getenv("MODBUS_RTU_SLAVE_ID", "1"))
    registers = [(int(a.split(":")[0]), int(a.split(":")[1])) for a in os.getenv("MODBUS_RTU_REGISTERS", "0:1").split(",") if ":" in a]
    client = ModbusRTUClient(port=port, baudrate=baudrate, slave_id=slave_id)
    while not stop_event.is_set():
        try:
            if not client._client or not client._client.connected:
                client.connect()
            for addr, count in registers:
                values = client.read_holding_registers(addr, count)
                if values:
                    for i, val in enumerate(values):
                        publisher.publish_event(
                            {
                                "source_protocol": "modbus_rtu",
                                "source_id": f"{port}:{slave_id}:hr/{addr+i}",
                                "asset_id": f"RTU-{slave_id}",
                                "tag": f"register_{addr+i}",
                                "value": float(val),
                                "quality": "good",
                                "unit": "",
                                "ts_source": utc_now(),
                            }
                        )
            await asyncio.sleep(settings.poll_seconds)
        except Exception:
            adapter_errors.labels(protocol="modbus_rtu").inc()
            client.disconnect()
            await asyncio.sleep(5)

async def run_opcua_discovery(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    """OPC UA discovery and subscription loop."""
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

async def main() -> None:
    settings = Settings()
    hierarchy = load_hierarchy("config/assets.yaml")
    stop_event = asyncio.Event()
    publisher = EdgePublisher(settings)
    start_http_server(settings.metrics_port)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows event loops do not support signal handlers here.
            pass

    tasks = []
    if "mqtt" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_mqtt(settings, publisher, stop_event)))
    if "opcua" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_opcua(settings, publisher, stop_event)))
    if "modbus" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_modbus(settings, publisher, stop_event)))
    if "modbus_rtu" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_modbus_rtu(settings, publisher, stop_event)))
    if "opcua_discovery" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_opcua_discovery(settings, publisher, stop_event)))

    try:
        await stop_event.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        publisher.flush()


if __name__ == "__main__":
    asyncio.run(main())

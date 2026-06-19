from __future__ import annotations

import asyncio
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
    def __init__(self, settings: Settings):
        self.settings = settings
        self.producer = Producer({"bootstrap.servers": settings.brokers, "client.id": "edge-ingest"})

    def publish_raw(self, protocol: str, source_id: str, payload: dict[str, Any]) -> None:
        self.producer.produce(
            self.settings.raw_topic,
            key=f"{protocol}:{source_id}".encode("utf-8"),
            value=to_json_bytes(payload),
        )
        self.producer.poll(0)

    def publish_event(self, payload: dict[str, Any]) -> None:
        protocol = str(payload.get("source_protocol", "unknown"))
        source_id = str(payload.get("source_id", "unknown"))
        self.publish_raw(protocol, source_id, payload)
        event, dlq = validate_event(payload)
        if dlq:
            self.producer.produce(self.settings.dlq_topic, key=source_id.encode("utf-8"), value=to_json_bytes(dlq))
            dlq_total.labels(protocol=protocol).inc()
            self.producer.poll(0)
            return

        assert event is not None
        key = event.asset_id.encode("utf-8")
        payload_bytes = to_json_bytes(event)
        self.producer.produce(self.settings.normalized_topic, key=key, value=payload_bytes)
        self.producer.produce(self.settings.legacy_topic, key=key, value=to_json_bytes(to_legacy_iot_event(event)))
        self.producer.poll(0)
        events_total.labels(protocol=event.source_protocol).inc()
        last_success_epoch.labels(protocol=event.source_protocol).set(time.time())
        observe_latency(event)

    def flush(self) -> None:
        self.producer.flush(10)


def observe_latency(event: IndustrialEvent) -> None:
    try:
        source_epoch = time.mktime(time.strptime(event.ts_source[:19], "%Y-%m-%dT%H:%M:%S"))
        ingest_latency.labels(protocol=event.source_protocol).observe(max(time.time() - source_epoch, 0))
    except Exception:
        return


def to_legacy_iot_event(event: IndustrialEvent) -> dict[str, Any]:
    tag = event.tag.lower()
    numeric_value = float(event.value) if isinstance(event.value, int | float | bool) else 0.0
    base = {
        "event_id": event.event_id,
        "device_id": event.asset_id,
        "site_id": event.site,
        "timestamp": event.ts_source,
        "source_protocol": event.source_protocol,
        "quality": event.quality,
        "schema_version": event.schema_version,
        "temperature_c": 48.0,
        "vibration_mm_s": 3.0,
        "pressure_bar": 6.2,
    }
    if "temp" in tag:
        base["temperature_c"] = numeric_value
    elif "vibration" in tag:
        base["vibration_mm_s"] = numeric_value
    elif "pressure" in tag:
        base["pressure_bar"] = numeric_value
    return base


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
            async with Client(settings.opcua_endpoint) as client:
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
                                "unit": unit_for(tag),
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
        client = ModbusTcpClient(settings.modbus_host, port=settings.modbus_port)
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


def unit_for(tag: str) -> str:
    lowered = tag.lower()
    if "temp" in lowered:
        return "c"
    if "vibration" in lowered:
        return "mm/s"
    if "pressure" in lowered:
        return "bar"
    return ""


async def main() -> None:
    settings = Settings()
    stop_event = asyncio.Event()
    publisher = EdgePublisher(settings)
    start_http_server(settings.metrics_port)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    tasks = []
    if "mqtt" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_mqtt(settings, publisher, stop_event)))
    if "opcua" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_opcua(settings, publisher, stop_event)))
    if "modbus" in settings.enabled_protocols:
        tasks.append(asyncio.create_task(run_modbus(settings, publisher, stop_event)))

    try:
        await stop_event.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        publisher.flush()


if __name__ == "__main__":
    asyncio.run(main())

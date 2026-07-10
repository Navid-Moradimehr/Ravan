from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from services.common.brokers import resolve_kafka_brokers
from services.common.connection_registry import ConnectionRegistry


@dataclass(frozen=True)
class SourceRuntime:
    connection_id: str
    source_protocol: str
    site_id: str
    endpoint: str = ""
    source_id: str = ""
    config: dict[str, Any] | None = None

    @property
    def options(self) -> dict[str, Any]:
        return self.config or {}


@dataclass(frozen=True)
class Settings:
    brokers: str = resolve_kafka_brokers("localhost:19092")
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
    mqtt_qos: int = int(os.getenv("MQTT_QOS", "1"))
    mqtt_retained_available: bool = os.getenv("MQTT_RETAINED", "true").strip().lower() in ("1", "true", "yes", "on")
    mqtt_will_topic: str = os.getenv("MQTT_WILL_TOPIC", "")
    mqtt_will_payload: str = os.getenv("MQTT_WILL_PAYLOAD", "")
    mqtt_will_qos: int = int(os.getenv("MQTT_WILL_QOS", "1"))
    mqtt_will_retain: bool = os.getenv("MQTT_WILL_RETAIN", "false").strip().lower() in ("1", "true", "yes", "on")
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
    historian_batch_size: int = int(os.getenv("EDGE_HISTORIAN_BATCH_SIZE", "1024"))
    mqtt_queue_size: int = int(os.getenv("EDGE_MQTT_QUEUE_SIZE", "10000"))
    max_message_bytes: int = int(os.getenv("EDGE_MAX_MESSAGE_BYTES", "1048576"))

    def source_connections(self) -> tuple[SourceRuntime, ...]:
        """Return enabled registry sources, or one legacy source per protocol.

        The fallback is intentional: existing Compose and CLI deployments do
        not need a registry file to keep working.
        """
        registry = ConnectionRegistry()
        configured = registry.list(enabled=True)
        if configured:
            return tuple(
                SourceRuntime(
                    connection_id=item.connection_id,
                    source_protocol=item.source_protocol,
                    site_id=item.site_id,
                    endpoint=item.endpoint,
                    source_id=item.source_id,
                    config=item.config,
                )
                for item in configured
            )
        return self._legacy_sources()

    def _legacy_sources(self) -> tuple[SourceRuntime, ...]:
        sources: list[SourceRuntime] = []
        if "mqtt" in self.enabled_protocols:
            sources.append(SourceRuntime("legacy-mqtt", "mqtt", os.getenv("SITE_ID", "demo-site"), f"mqtt://{self.mqtt_host}:{self.mqtt_port}", "legacy-mqtt", {"topic": self.mqtt_topic}))
        if "opcua" in self.enabled_protocols:
            sources.append(SourceRuntime("legacy-opcua", "opcua", os.getenv("SITE_ID", "demo-site"), self.opcua_endpoint, "legacy-opcua", {"nodes": list(self.opcua_nodes)}))
        if "modbus" in self.enabled_protocols:
            sources.append(SourceRuntime("legacy-modbus", "modbus", os.getenv("SITE_ID", "demo-site"), f"modbus://{self.modbus_host}:{self.modbus_port}", "legacy-modbus", {}))
        if "modbus_rtu" in self.enabled_protocols:
            sources.append(SourceRuntime("legacy-modbus-rtu", "modbus_rtu", os.getenv("SITE_ID", "demo-site"), "", "legacy-modbus-rtu", {}))
        if "opcua_discovery" in self.enabled_protocols:
            sources.append(SourceRuntime("legacy-opcua-discovery", "opcua_discovery", os.getenv("SITE_ID", "demo-site"), "", "legacy-opcua-discovery", {}))
        return tuple(sources)

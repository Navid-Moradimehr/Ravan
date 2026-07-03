from __future__ import annotations

import os
from dataclasses import dataclass


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

"""Connector Marketplace — catalog of pre-built source/sink connectors.

Open-source connectors for SQL, REST, file, cloud, MQTT, OPC UA, Modbus.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ConnectorSpec:
    connector_id: str
    name: str
    description: str
    category: str  # source, sink, transform
    protocol: str
    config_schema: list[dict[str, Any]]
    icon: str = "plug"
    documentation_url: str = ""
    open_source: bool = True


CONNECTOR_CATALOG: list[ConnectorSpec] = [
    ConnectorSpec(
        connector_id="mqtt-source",
        name="MQTT Source",
        description="Subscribe to MQTT topics and ingest messages",
        category="source",
        protocol="mqtt",
        config_schema=[
            {"name": "host", "type": "string", "required": True, "default": "localhost"},
            {"name": "port", "type": "int", "required": True, "default": 1883},
            {"name": "topic", "type": "string", "required": True},
            {"name": "qos", "type": "int", "required": False, "default": 1},
        ],
        icon="radio",
        documentation_url="https://github.com/eclipse/paho.mqtt.python",
    ),
    ConnectorSpec(
        connector_id="opcua-source",
        name="OPC UA Source",
        description="Browse and subscribe to OPC UA server nodes",
        category="source",
        protocol="opcua",
        config_schema=[
            {"name": "endpoint", "type": "string", "required": True},
            {"name": "nodes", "type": "list", "required": True},
            {"name": "subscription_rate_ms", "type": "int", "required": False, "default": 1000},
        ],
        icon="server",
        documentation_url="https://github.com/FreeOpcUa/opcua-asyncua",
    ),
    ConnectorSpec(
        connector_id="modbus-tcp-source",
        name="Modbus TCP Source",
        description="Poll Modbus TCP holding/input registers",
        category="source",
        protocol="modbus_tcp",
        config_schema=[
            {"name": "host", "type": "string", "required": True},
            {"name": "port", "type": "int", "required": True, "default": 502},
            {"name": "slave_id", "type": "int", "required": True, "default": 1},
            {"name": "registers", "type": "list", "required": True},
        ],
        icon="cpu",
        documentation_url="https://github.com/pymodbus-dev/pymodbus",
    ),
    ConnectorSpec(
        connector_id="modbus-rtu-source",
        name="Modbus RTU Source",
        description="Poll Modbus RTU serial devices",
        category="source",
        protocol="modbus_rtu",
        config_schema=[
            {"name": "port", "type": "string", "required": True, "default": "/dev/ttyUSB0"},
            {"name": "baudrate", "type": "int", "required": True, "default": 9600},
            {"name": "slave_id", "type": "int", "required": True, "default": 1},
            {"name": "registers", "type": "list", "required": True},
        ],
        icon="serial",
        documentation_url="https://github.com/pymodbus-dev/pymodbus",
    ),
    ConnectorSpec(
        connector_id="sql-source",
        name="SQL Source",
        description="Query SQL databases and stream rows",
        category="source",
        protocol="sql",
        config_schema=[
            {"name": "connection_string", "type": "string", "required": True},
            {"name": "query", "type": "string", "required": True},
            {"name": "poll_interval_seconds", "type": "int", "required": False, "default": 60},
        ],
        icon="database",
        documentation_url="https://github.com/psycopg/psycopg2",
    ),
    ConnectorSpec(
        connector_id="rest-source",
        name="REST API Source",
        description="Poll REST endpoints and ingest JSON responses",
        category="source",
        protocol="http",
        config_schema=[
            {"name": "url", "type": "string", "required": True},
            {"name": "method", "type": "string", "required": False, "default": "GET"},
            {"name": "headers", "type": "dict", "required": False, "default": {}},
            {"name": "poll_interval_seconds", "type": "int", "required": False, "default": 60},
        ],
        icon="globe",
        documentation_url="https://github.com/encode/httpx",
    ),
    ConnectorSpec(
        connector_id="file-source",
        name="CSV/File Source",
        description="Watch and ingest CSV or JSON files from a directory",
        category="source",
        protocol="file",
        config_schema=[
            {"name": "path", "type": "string", "required": True},
            {"name": "format", "type": "string", "required": True, "default": "csv"},
            {"name": "watch", "type": "bool", "required": False, "default": True},
        ],
        icon="file",
        documentation_url="https://docs.python.org/3/library/csv.html",
    ),
    ConnectorSpec(
        connector_id="mqtt-sink",
        name="MQTT Sink",
        description="Publish processed events to an MQTT broker",
        category="sink",
        protocol="mqtt",
        config_schema=[
            {"name": "host", "type": "string", "required": True},
            {"name": "port", "type": "int", "required": True, "default": 1883},
            {"name": "topic_template", "type": "string", "required": True},
        ],
        icon="radio",
        documentation_url="https://github.com/eclipse/paho.mqtt.python",
    ),
    ConnectorSpec(
        connector_id="amqp-sink",
        name="AMQP Sink",
        description="Publish events to an AMQP exchange (RabbitMQ, etc.)",
        category="sink",
        protocol="amqp",
        config_schema=[
            {"name": "url", "type": "string", "required": True},
            {"name": "exchange", "type": "string", "required": True},
            {"name": "routing_key_template", "type": "string", "required": True},
        ],
        icon="message-square",
        documentation_url="https://github.com/pika/pika",
    ),
    ConnectorSpec(
        connector_id="timescale-sink",
        name="TimescaleDB Sink",
        description="Store events in TimescaleDB hypertables",
        category="sink",
        protocol="postgresql",
        config_schema=[
            {"name": "connection_string", "type": "string", "required": True},
            {"name": "table", "type": "string", "required": True, "default": "industrial_events"},
        ],
        icon="database",
        documentation_url="https://github.com/timescale/timescaledb",
    ),
    ConnectorSpec(
        connector_id="kafka-sink",
        name="Kafka Sink",
        description="Produce events to a Kafka topic",
        category="sink",
        protocol="kafka",
        config_schema=[
            {"name": "brokers", "type": "string", "required": True},
            {"name": "topic", "type": "string", "required": True},
        ],
        icon="message-circle",
        documentation_url="https://github.com/confluentinc/confluent-kafka-python",
    ),
    ConnectorSpec(
        connector_id="webhook-sink",
        name="Webhook Sink",
        description="POST events to HTTP webhooks",
        category="sink",
        protocol="http",
        config_schema=[
            {"name": "url", "type": "string", "required": True},
            {"name": "headers", "type": "dict", "required": False, "default": {}},
            {"name": "events", "type": "list", "required": False, "default": ["alarm", "anomaly"]},
        ],
        icon="webhook",
        documentation_url="https://github.com/encode/httpx",
    ),
]


def list_connectors(category: str | None = None, protocol: str | None = None) -> list[dict[str, Any]]:
    results = CONNECTOR_CATALOG
    if category:
        results = [c for c in results if c.category == category]
    if protocol:
        results = [c for c in results if c.protocol == protocol]
    return [c.__dict__ for c in results]


def get_connector(connector_id: str) -> ConnectorSpec | None:
    for c in CONNECTOR_CATALOG:
        if c.connector_id == connector_id:
            return c
    return None

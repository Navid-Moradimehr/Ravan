"""MQTT Sparkplug B encoder/decoder for industrial IoT.

Sparkplug B is an open specification for MQTT-based industrial device
communication. Uses Protocol Buffers for efficient binary encoding.

Open-source: https://github.com/eclipse/tahu
Specification: https://sparkplug.eclipse.org/
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from google.protobuf import json_format
    from google.protobuf.timestamp_pb2 import Timestamp
    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False

logger = logging.getLogger(__name__)


def parse_lifecycle_topic(topic: str) -> dict[str, str] | None:
    """Return the Sparkplug lifecycle meaning encoded in a topic."""
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "spBv1.0":
        return None
    packet_type = parts[2].upper()
    states = {"NBIRTH": "connected", "DBIRTH": "connected", "NDEATH": "disconnected", "DDEATH": "disconnected"}
    state = states.get(packet_type)
    if state is None:
        return None
    return {
        "group_id": parts[1],
        "packet_type": packet_type,
        "state": state,
        "edge_node_id": parts[3],
        "device_id": parts[4] if len(parts) > 4 else "",
    }


def lifecycle_event(topic: str, site: str, source_id: str, lifecycle: dict[str, str]) -> dict[str, Any]:
    """Build a canonical state event for a Sparkplug birth/death packet."""
    asset_id = lifecycle.get("device_id") or lifecycle.get("edge_node_id") or source_id or topic
    return {
        "source_protocol": "sparkplug_b",
        "source_id": source_id or topic,
        "asset_id": asset_id,
        "tag": "__sparkplug_lifecycle__",
        "value": lifecycle["state"],
        "value_kind": "state",
        "quality": "good",
        "site": site,
        "ts_source": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sparkplug_topic": topic,
        "sparkplug_packet_type": lifecycle["packet_type"],
    }


def decode_binary_payload(payload: bytes, topic: str, site: str, source_id: str) -> list[dict[str, Any]]:
    """Decode a real Sparkplug B protobuf payload through TahUtils/Eclipse Tahu."""
    try:
        from tahutils.parse import parse_payload_to_metric_list, payload_from_string
    except ImportError as exc:
        raise RuntimeError("Sparkplug B requires the optional tahutils dependency") from exc
    parsed_payload = payload_from_string(payload)
    metrics = parse_payload_to_metric_list(parsed_payload)
    topic_parts = topic.split("/")
    asset_id = topic_parts[-1] if topic_parts and topic_parts[-1] else source_id
    timestamp = parsed_payload.timestamp or int(time.time() * 1000)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp / 1000))
    return [
        {
            "source_protocol": "sparkplug_b",
            "source_id": f"{source_id}:{metric.name}",
            "asset_id": asset_id,
            "tag": metric.name,
            "value": metric.value,
            "quality": "good",
            "site": site,
            "ts_source": ts,
            "sparkplug_topic": topic,
            "sparkplug_datatype": metric.datatype,
            "sparkplug_timestamp": metric.timestamp,
        }
        for metric in metrics
        if not metric.is_null and metric.value is not None
    ]


# Sparkplug B metric types (simplified)
SPARKPLUG_METRIC_TYPES = {
    "Int8": 1,
    "Int16": 2,
    "Int32": 3,
    "Int64": 4,
    "UInt8": 5,
    "UInt16": 6,
    "UInt32": 7,
    "UInt64": 8,
    "Float": 9,
    "Double": 10,
    "Boolean": 11,
    "String": 12,
    "DateTime": 13,
    "Text": 14,
    "UUID": 15,
    "DataSet": 16,
    "Bytes": 17,
    "File": 18,
    "Template": 19,
}


@dataclass
class SparkplugMetric:
    """A single Sparkplug B metric."""
    name: str
    value: Any
    datatype: str = "Double"
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    is_historical: bool = False
    is_transient: bool = False
    is_null: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "datatype": self.datatype,
            "timestamp": self.timestamp,
            "isHistorical": self.is_historical,
            "isTransient": self.is_transient,
            "isNull": self.is_null,
            "metadata": self.metadata,
        }


@dataclass
class SparkplugPayload:
    """Sparkplug B payload containing metrics."""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    metrics: list[SparkplugMetric] = field(default_factory=list)
    seq: int | None = None
    uuid: str | None = None
    body: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "metrics": [m.to_dict() for m in self.metrics],
            "seq": self.seq,
            "uuid": self.uuid,
        }


class SparkplugBEncoder:
    """Encode industrial events to Sparkplug B format."""

    @staticmethod
    def encode_metric(metric: SparkplugMetric) -> dict[str, Any]:
        """Encode a single metric to Sparkplug B JSON representation."""
        return metric.to_dict()

    @staticmethod
    def encode_payload(payload: SparkplugPayload) -> dict[str, Any]:
        """Encode a full payload to Sparkplug B JSON representation."""
        return payload.to_dict()

    @staticmethod
    def from_industrial_event(event: dict[str, Any]) -> SparkplugPayload:
        """Convert an industrial event to Sparkplug B payload."""
        metric = SparkplugMetric(
            name=f"{event.get('asset_id', 'unknown')}/{event.get('tag', 'unknown')}",
            value=event.get("value", 0),
            datatype=SparkplugBEncoder._infer_datatype(event.get("value")),
            timestamp=int(
                time.mktime(time.strptime(event.get("ts_ingest", ""), "%Y-%m-%dT%H:%M:%S.%f"))
                * 1000
            ) if "ts_ingest" in event else int(time.time() * 1000),
            metadata={
                "source_protocol": event.get("source_protocol", "unknown"),
                "quality": event.get("quality", "good"),
                "unit": event.get("unit", ""),
                "site": event.get("site", ""),
                "line": event.get("line", ""),
            },
        )
        return SparkplugPayload(metrics=[metric])

    @staticmethod
    def _infer_datatype(value: Any) -> str:
        """Infer Sparkplug datatype from Python value."""
        if isinstance(value, bool):
            return "Boolean"
        elif isinstance(value, int):
            return "Int64"
        elif isinstance(value, float):
            return "Double"
        elif isinstance(value, str):
            return "String"
        elif isinstance(value, bytes):
            return "Bytes"
        return "String"


class SparkplugBDecoder:
    """Decode Sparkplug B payloads to industrial events."""

    @staticmethod
    def decode_metric(metric_dict: dict[str, Any]) -> SparkplugMetric:
        """Decode a Sparkplug B metric from JSON."""
        return SparkplugMetric(
            name=metric_dict.get("name", ""),
            value=metric_dict.get("value"),
            datatype=metric_dict.get("datatype", "Double"),
            timestamp=metric_dict.get("timestamp", int(time.time() * 1000)),
            is_historical=metric_dict.get("isHistorical", False),
            is_transient=metric_dict.get("isTransient", False),
            is_null=metric_dict.get("isNull", False),
            metadata=metric_dict.get("metadata", {}),
        )

    @staticmethod
    def decode_payload(payload_dict: dict[str, Any]) -> SparkplugPayload:
        """Decode a Sparkplug B payload from JSON."""
        metrics = [
            SparkplugBDecoder.decode_metric(m)
            for m in payload_dict.get("metrics", [])
        ]
        return SparkplugPayload(
            timestamp=payload_dict.get("timestamp", int(time.time() * 1000)),
            metrics=metrics,
            seq=payload_dict.get("seq"),
            uuid=payload_dict.get("uuid"),
        )

    @staticmethod
    def to_industrial_event(payload: SparkplugPayload) -> dict[str, Any]:
        """Convert Sparkplug B payload to industrial event format."""
        if not payload.metrics:
            return {}

        metric = payload.metrics[0]
        parts = metric.name.split("/", 1)
        asset_id = parts[0] if len(parts) > 0 else "unknown"
        tag = parts[1] if len(parts) > 1 else "unknown"

        return {
            "source_protocol": "sparkplug_b",
            "asset_id": asset_id,
            "tag": tag,
            "value": metric.value,
            "quality": metric.metadata.get("quality", "good"),
            "unit": metric.metadata.get("unit", ""),
            "site": metric.metadata.get("site", "demo-site"),
            "line": metric.metadata.get("line", "line-01"),
            "ts_ingest": time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.localtime(payload.timestamp / 1000),
            ),
            "schema_version": 1,
        }


class SparkplugTopicBuilder:
    """Build Sparkplug B MQTT topics."""

    @staticmethod
    def node_birth(group_id: str, edge_node_id: str) -> str:
        return f"spBv1.0/{group_id}/NBIRTH/{edge_node_id}"

    @staticmethod
    def node_death(group_id: str, edge_node_id: str) -> str:
        return f"spBv1.0/{group_id}/NDEATH/{edge_node_id}"

    @staticmethod
    def device_birth(group_id: str, edge_node_id: str, device_id: str) -> str:
        return f"spBv1.0/{group_id}/DBIRTH/{edge_node_id}/{device_id}"

    @staticmethod
    def device_death(group_id: str, edge_node_id: str, device_id: str) -> str:
        return f"spBv1.0/{group_id}/DDEATH/{edge_node_id}/{device_id}"

    @staticmethod
    def node_data(group_id: str, edge_node_id: str) -> str:
        return f"spBv1.0/{group_id}/NDATA/{edge_node_id}"

    @staticmethod
    def device_data(group_id: str, edge_node_id: str, device_id: str) -> str:
        return f"spBv1.0/{group_id}/DDATA/{edge_node_id}/{device_id}"

    @staticmethod
    def node_command(group_id: str, edge_node_id: str) -> str:
        return f"spBv1.0/{group_id}/NCMD/{edge_node_id}"

    @staticmethod
    def device_command(group_id: str, edge_node_id: str, device_id: str) -> str:
        return f"spBv1.0/{group_id}/DCMD/{edge_node_id}/{device_id}"

    @staticmethod
    def state(group_id: str) -> str:
        return f"spBv1.0/{group_id}/STATE/{group_id}"

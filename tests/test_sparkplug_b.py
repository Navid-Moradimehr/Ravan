"""Tests for Sparkplug B encoder/decoder."""
from __future__ import annotations

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "edge_ingest"))

from mqtt_sparkplug_b import (
    SparkplugMetric,
    SparkplugPayload,
    SparkplugBEncoder,
    SparkplugBDecoder,
    SparkplugTopicBuilder,
    parse_lifecycle_topic,
    lifecycle_event,
    build_rebirth_command,
)


def test_sparkplug_metric():
    metric = SparkplugMetric(
        name="PUMP-01/Temperature",
        value=51.2,
        datatype="Double",
    )
    assert metric.name == "PUMP-01/Temperature"
    assert metric.value == 51.2
    assert metric.datatype == "Double"


def test_sparkplug_payload():
    payload = SparkplugPayload(
        metrics=[
            SparkplugMetric(name="Tag1", value=100),
            SparkplugMetric(name="Tag2", value=200),
        ]
    )
    assert len(payload.metrics) == 2
    assert payload.metrics[0].name == "Tag1"


def test_encoder_from_industrial_event():
    event = {
        "asset_id": "PUMP-01",
        "tag": "Temperature",
        "value": 51.2,
        "source_protocol": "opcua",
        "quality": "good",
        "unit": "°C",
        "site": "demo-site",
        "line": "line-01",
    }
    payload = SparkplugBEncoder.from_industrial_event(event)
    assert len(payload.metrics) == 1
    assert payload.metrics[0].name == "PUMP-01/Temperature"
    assert payload.metrics[0].value == 51.2
    assert payload.metrics[0].metadata["unit"] == "°C"


def test_decoder_to_industrial_event():
    payload = SparkplugPayload(
        metrics=[
            SparkplugMetric(
                name="PUMP-01/Temperature",
                value=51.2,
                datatype="Double",
                metadata={"quality": "good", "unit": "°C"},
            )
        ]
    )
    event = SparkplugBDecoder.to_industrial_event(payload)
    assert event["asset_id"] == "PUMP-01"
    assert event["tag"] == "Temperature"
    assert event["value"] == 51.2
    assert event["source_protocol"] == "sparkplug_b"
    assert event["ts_source"].endswith("+00:00")
    assert event["ts_ingest"].endswith("+00:00")


def test_roundtrip_conversion():
    original = {
        "asset_id": "PUMP-01",
        "tag": "Temperature",
        "value": 51.2,
        "source_protocol": "opcua",
        "quality": "good",
        "unit": "°C",
    }
    payload = SparkplugBEncoder.from_industrial_event(original)
    event = SparkplugBDecoder.to_industrial_event(payload)
    assert event["asset_id"] == original["asset_id"]
    assert event["tag"] == original["tag"]
    assert event["value"] == original["value"]


def test_topic_builder():
    assert SparkplugTopicBuilder.node_birth("group1", "node1") == "spBv1.0/group1/NBIRTH/node1"
    assert SparkplugTopicBuilder.node_death("group1", "node1") == "spBv1.0/group1/NDEATH/node1"
    assert SparkplugTopicBuilder.device_birth("group1", "node1", "device1") == "spBv1.0/group1/DBIRTH/node1/device1"
    assert SparkplugTopicBuilder.device_data("group1", "node1", "device1") == "spBv1.0/group1/DDATA/node1/device1"
    assert SparkplugTopicBuilder.node_command("group1", "node1") == "spBv1.0/group1/NCMD/node1"
    assert SparkplugTopicBuilder.state("group1") == "spBv1.0/group1/STATE/group1"


def test_sparkplug_lifecycle_topics_become_state_events():
    lifecycle = parse_lifecycle_topic("spBv1.0/group1/NDEATH/node1/device1")
    assert lifecycle == {"group_id": "group1", "packet_type": "NDEATH", "state": "disconnected", "edge_node_id": "node1", "device_id": "device1"}
    event = lifecycle_event("spBv1.0/group1/NDEATH/node1/device1", "plant-a", "edge-1", lifecycle)
    assert event["tag"] == "__sparkplug_lifecycle__"
    assert event["value"] == "disconnected"
    assert event["value_kind"] == "state"


def test_sparkplug_rebirth_command_is_binary_tahu_payload():
    payload = build_rebirth_command()
    assert isinstance(payload, bytes)
    assert payload


def test_infer_datatype():
    assert SparkplugBEncoder._infer_datatype(42) == "Int64"
    assert SparkplugBEncoder._infer_datatype(3.14) == "Double"
    assert SparkplugBEncoder._infer_datatype(True) == "Boolean"
    assert SparkplugBEncoder._infer_datatype("hello") == "String"
    assert SparkplugBEncoder._infer_datatype(b"bytes") == "Bytes"

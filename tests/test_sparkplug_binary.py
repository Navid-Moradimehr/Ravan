from __future__ import annotations

import pytest


def test_sparkplug_binary_decoder_is_available_when_tahutils_is_installed():
    pytest.importorskip("tahutils")
    from tahutils.tahu import sparkplug_b as spb

    from services.edge_ingest.mqtt_sparkplug_b import decode_binary_payload

    payload = spb.Payload()
    metric = payload.metrics.add()
    metric.name = "Temperature"
    metric.datatype = spb.MetricDataType.Double
    metric.double_value = 42.5
    metric.timestamp = 1700000000000

    events = decode_binary_payload(payload.SerializeToString(), "spBv1.0/group/DDATA/node/device", "plant-a", "gateway-1")

    assert events[0]["source_protocol"] == "sparkplug_b"
    assert events[0]["value"] == 42.5
    assert events[0]["sparkplug_topic"].startswith("spBv1.0/")

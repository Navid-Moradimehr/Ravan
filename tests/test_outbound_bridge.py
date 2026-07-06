from __future__ import annotations

import json

from services.edge_ingest.outbound_bridge import OutboundBridge


class _FakeMsg:
    def __init__(self, value: bytes, topic: str = "iot.processed", partition: int = 0, offset: int = 7):
        self._value = value
        self._topic = topic
        self._partition = partition
        self._offset = offset

    def value(self):
        return self._value

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset


def _make_bridge(monkeypatch, mqtt_host="mqtt.local", amqp_url=None) -> tuple[OutboundBridge, list]:
    bridge = OutboundBridge(mqtt_host=mqtt_host, amqp_url=amqp_url)
    commits: list = []

    class FakeConsumer:
        def commit(self, offset=None, asynchronous=True):
            commits.append(offset)

    bridge._consumer = FakeConsumer()
    return bridge, commits


def test_outbound_bridge_commits_on_successful_forward(monkeypatch):
    bridge, commits = _make_bridge(monkeypatch)
    monkeypatch.setattr(bridge, "_forward_mqtt", lambda event: True)

    msg = _FakeMsg(json.dumps({"asset_id": "Pump-01", "tag": "Temperature"}).encode("utf-8"))
    bridge._handle_message(msg)

    assert len(commits) == 1
    assert commits[0].offset == 8  # offset + 1
    assert commits[0].topic == "iot.processed"
    assert commits[0].partition == 0


def test_outbound_bridge_skips_commit_on_forward_failure(monkeypatch):
    bridge, commits = _make_bridge(monkeypatch)
    monkeypatch.setattr(bridge, "_forward_mqtt", lambda event: False)

    msg = _FakeMsg(json.dumps({"asset_id": "Pump-01", "tag": "Temperature"}).encode("utf-8"))
    bridge._handle_message(msg)

    assert commits == []


def test_outbound_bridge_commits_poison_message(monkeypatch):
    bridge, commits = _make_bridge(monkeypatch)
    monkeypatch.setattr(bridge, "_forward_mqtt", lambda event: True)

    msg = _FakeMsg(b"not-json{")
    bridge._handle_message(msg)

    assert len(commits) == 1
    assert commits[0].offset == 8


def test_outbound_bridge_requires_all_forwarders_to_succeed(monkeypatch):
    bridge, commits = _make_bridge(monkeypatch, amqp_url="amqp://guest:guest@rabbit")
    monkeypatch.setattr(bridge, "_forward_mqtt", lambda event: True)
    monkeypatch.setattr(bridge, "_forward_amqp", lambda event: False)

    msg = _FakeMsg(json.dumps({"asset_id": "Pump-01"}).encode("utf-8"))
    bridge._handle_message(msg)

    assert commits == []


def test_outbound_bridge_consumer_disables_auto_commit():
    bridge = OutboundBridge()
    conf_seen: dict = {}

    class FakeConsumer:
        def __init__(self, conf):
            conf_seen.update(conf)

        def subscribe(self, topics):
            pass

    import services.edge_ingest.outbound_bridge as mod

    orig = mod.Consumer
    mod.Consumer = FakeConsumer
    try:
        bridge._start_consumer()
    finally:
        mod.Consumer = orig

    assert conf_seen["enable.auto.commit"] is False
    assert conf_seen["enable.auto.offset.store"] is False
    assert conf_seen["group.id"] == "outbound-bridge"
    assert conf_seen["auto.offset.reset"] == "latest"

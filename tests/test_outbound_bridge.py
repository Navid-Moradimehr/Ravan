"""Tests for MQTT/AMQP outbound bridge."""
import json
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, "services/api_service")
from main import app

client = TestClient(app)


def test_get_bridge_config_not_set():
    resp = client.get("/api/v1/outbound-bridge/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["config"] is None


def test_set_and_get_bridge_config():
    config = {
        "enabled": True,
        "config": {
            "mqtt_host": "test.mqtt.local",
            "mqtt_port": 1883,
            "mqtt_use_tls": False,
            "mqtt_topic_template": "plant/{{asset_id}}/{{tag}}",
            "amqp_url": "amqp://guest:guest@localhost:5672/%2F",
            "amqp_exchange": "industrial.events",
            "amqp_routing_key": "{{asset_id}}.{{tag}}"
        }
    }
    resp = client.post("/api/v1/outbound-bridge/config", json=config)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["enabled"] is True

    resp = client.get("/api/v1/outbound-bridge/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["config"]["mqtt_host"] == "test.mqtt.local"


def test_publish_without_bridge_fails():
    # Reset state
    client.post("/api/v1/outbound-bridge/config", json={
        "enabled": False,
        "config": {
            "mqtt_host": None,
            "mqtt_port": 1883,
            "mqtt_use_tls": False,
            "mqtt_topic_template": "industrial/{{asset_id}}/{{tag}}",
            "amqp_url": None,
            "amqp_exchange": "industrial.events",
            "amqp_routing_key": "{{asset_id}}.{{tag}}"
        }
    })
    resp = client.post("/api/v1/outbound-bridge/enable", params={"enabled": False})
    assert resp.status_code == 200

    resp = client.post("/api/v1/outbound-bridge/publish", json={
        "asset_id": "asset-01",
        "tag": "temperature",
        "value": 42.0
    })
    assert resp.status_code == 400


def test_enable_disable_bridge():
    client.post("/api/v1/outbound-bridge/config", json={
        "enabled": True,
        "config": {
            "mqtt_host": "test.mqtt.local",
            "mqtt_port": 1883,
            "mqtt_use_tls": False,
            "mqtt_topic_template": "industrial/{{asset_id}}/{{tag}}",
            "amqp_url": None,
            "amqp_exchange": "industrial.events",
            "amqp_routing_key": "{{asset_id}}.{{tag}}"
        }
    })
    resp = client.post("/api/v1/outbound-bridge/enable", params={"enabled": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False

    resp = client.post("/api/v1/outbound-bridge/enable", params={"enabled": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True


def test_render_topic():
    sys.path.insert(0, "services/api_service")
    from main import _render_topic
    assert _render_topic("plant/{{asset_id}}/{{tag}}", {"asset_id": "A1", "tag": "T1"}) == "plant/A1/T1"

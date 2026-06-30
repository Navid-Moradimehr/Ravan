from __future__ import annotations

import json
from datetime import datetime
from typing import Any


_outbound_bridge_state: Any | None = None


def _render_topic(template: str, event: dict[str, Any]) -> str:
    return template.replace("{{asset_id}}", event.get("asset_id", "")).replace("{{tag}}", event.get("tag", ""))


def set_outbound_bridge_state(state: Any) -> dict[str, Any]:
    global _outbound_bridge_state
    _outbound_bridge_state = state
    return {"ok": True, "enabled": state.enabled, "config": state.config.model_dump()}


def get_outbound_bridge_state() -> dict[str, Any]:
    if _outbound_bridge_state is None:
        return {"enabled": False, "config": None}
    return {
        "enabled": _outbound_bridge_state.enabled,
        "config": _outbound_bridge_state.config.model_dump(),
    }


def set_outbound_bridge_enabled(enabled: bool) -> dict[str, Any]:
    global _outbound_bridge_state
    if _outbound_bridge_state is None:
        raise ValueError("Bridge config not set")
    _outbound_bridge_state.enabled = enabled
    return {"ok": True, "enabled": enabled}


def publish_outbound_event(event: dict[str, Any]) -> dict[str, Any]:
    if _outbound_bridge_state is None or not _outbound_bridge_state.enabled:
        raise ValueError("Outbound bridge not enabled")

    config = _outbound_bridge_state.config
    payload = dict(event)
    if payload.get("timestamp") is None:
        payload["timestamp"] = datetime.utcnow().isoformat()

    results = []
    if config.mqtt_host:
        results.append(_publish_mqtt(config, payload))
    if config.amqp_url:
        results.append(_publish_amqp(config, payload))
    if not results:
        raise ValueError("No outbound protocol configured")
    return {"ok": all(r.get("ok") for r in results), "results": results}


def _publish_mqtt(config: Any, event: dict[str, Any]) -> dict[str, Any]:
    try:
        import paho.mqtt.publish as mqtt_publish

        topic = _render_topic(config.mqtt_topic_template, event)
        payload = json.dumps(event)
        mqtt_publish.single(
            topic,
            payload=payload,
            hostname=config.mqtt_host,
            port=config.mqtt_port,
            tls={} if config.mqtt_use_tls else None,
        )
        return {"ok": True, "protocol": "mqtt", "topic": topic}
    except Exception as e:
        return {"ok": False, "protocol": "mqtt", "error": str(e)}


def _publish_amqp(config: Any, event: dict[str, Any]) -> dict[str, Any]:
    try:
        import pika

        params = pika.URLParameters(config.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange=config.amqp_exchange, exchange_type="topic", durable=True)
        routing_key = _render_topic(config.amqp_routing_key, event)
        channel.basic_publish(
            exchange=config.amqp_exchange,
            routing_key=routing_key,
            body=json.dumps(event).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
        connection.close()
        return {"ok": True, "protocol": "amqp", "routing_key": routing_key}
    except Exception as e:
        return {"ok": False, "protocol": "amqp", "error": str(e)}

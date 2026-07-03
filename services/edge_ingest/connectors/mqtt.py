from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from paho.mqtt import client as mqtt

from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import EdgePublisher, adapter_errors, adapter_reconnects, dlq_total
from services.edge_ingest.settings import Settings


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
    mqtt_ca_cert = os.getenv("MQTT_CA_CERT", "")
    mqtt_certfile = os.getenv("MQTT_CERTFILE", "")
    mqtt_keyfile = os.getenv("MQTT_KEYFILE", "")
    if mqtt_ca_cert:
        client.tls_set(
            ca_certs=mqtt_ca_cert,
            certfile=mqtt_certfile or None,
            keyfile=mqtt_keyfile or None,
        )
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

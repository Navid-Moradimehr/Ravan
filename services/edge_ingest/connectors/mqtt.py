from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from paho.mqtt import client as mqtt

from services.edge_ingest.model import utc_now
from services.edge_ingest.publisher import (
    EdgePublisher,
    adapter_errors,
    adapter_reconnects,
    dlq_total,
    overflow_total,
)
from services.edge_ingest.settings import Settings


def enqueue_mqtt_message(
    queue: asyncio.Queue,
    payload: Any,
    publisher: EdgePublisher,
    source_id: str,
) -> None:
    """Enqueue a decoded MQTT payload, routing to the DLQ when saturated.

    Called from the paho network thread via ``on_message``. When the bounded
    decoupling queue is full (producer can't keep up) the message is routed to
    the DLQ and an overflow counter is bumped so the loss is observable instead
    of silent.
    """
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        overflow_total.labels(reason="mqtt_queue_full").inc()
        dlq_total.labels(protocol="mqtt").inc()
        publisher.publish_event(
            {
                "source_protocol": "mqtt",
                "source_id": source_id,
                "asset_id": "",
                "tag": "",
                "value": str(payload),
                "quality": "bad",
                "ts_source": utc_now(),
                "error": "mqtt_queue_full",
            }
        )


async def run_mqtt(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event) -> None:
    """MQTT adapter with a bounded asyncio decoupling queue.

    paho's network thread calls ``on_message`` on its own loop, so producing to
    Kafka directly there couples broker backpressure to the MQTT client. We
    instead enqueue decoded payloads onto a bounded :class:`asyncio.Queue` and
    drain it on the event loop.
    """

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=settings.mqtt_queue_size)

    async def _drain_queue() -> None:
        loop = asyncio.get_running_loop()
        while True:
            item = await queue.get()
            if item is None:
                return
            try:
                await loop.run_in_executor(None, publisher.publish_event, item)
            except Exception as exc:  # pragma: no cover - publisher already isolates failures
                dlq_total.labels(protocol="mqtt").inc()
                publisher.publish_event(
                    {
                        "source_protocol": "mqtt",
                        "source_id": item.get("source_id", ""),
                        "asset_id": "",
                        "tag": "",
                        "value": str(item),
                        "quality": "bad",
                        "ts_source": utc_now(),
                        "error": str(exc),
                    }
                )

    drainer = asyncio.create_task(_drain_queue())

    def on_connect(client: mqtt.Client, _userdata: object, _flags: dict[str, Any], reason_code: int, _properties: object = None) -> None:
        if reason_code == 0:
            client.subscribe(settings.mqtt_topic)
        else:
            adapter_errors.labels(protocol="mqtt").inc()

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
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
            return
        source_id = payload.get("source_id", message.topic) if isinstance(payload, dict) else message.topic
        enqueue_mqtt_message(queue, payload, publisher, source_id)

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
    try:
        while not stop_event.is_set():
            try:
                client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
                client.loop_start()
                await stop_event.wait()
                break
            except Exception:
                adapter_errors.labels(protocol="mqtt").inc()
                adapter_reconnects.labels(protocol="mqtt").inc()
                await asyncio.sleep(3)
    finally:
        client.loop_stop()
        client.disconnect()
        await queue.put(None)
        try:
            await asyncio.wait_for(drainer, timeout=10)
        except asyncio.TimeoutError:
            drainer.cancel()

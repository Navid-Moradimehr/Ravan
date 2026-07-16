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
from services.edge_ingest.source_health import mark_mapping_result
from services.edge_ingest.settings import Settings, SourceRuntime
from services.edge_ingest.source_health import mark_source, mark_source_success
from services.edge_ingest.credentials import CredentialResolutionError, resolve_credentials


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


async def run_mqtt(settings: Settings, publisher: EdgePublisher, stop_event: asyncio.Event, source: SourceRuntime | None = None) -> None:
    """MQTT adapter with a bounded asyncio decoupling queue.

    paho's network thread calls ``on_message`` on its own loop, so producing to
    Kafka directly there couples broker backpressure to the MQTT client. We
    instead enqueue decoded payloads onto a bounded :class:`asyncio.Queue` and
    drain it on the event loop.

    MQTT delivery options are configurable via ``Settings``: QoS level for the
    subscription, and an optional Last Will and Testament so an ungraceful
    adapter disconnect is signalled to downstream consumers. Retained-message
    availability is declared so operators know whether the broker retains the
    last known good value per topic.
    """

    source = source or settings.source_connections()[0]
    options = source.options
    sparkplug_mode = source.source_protocol == "sparkplug_b" or str(options.get("payload_mode", "")).lower() == "sparkplug_b"
    topic_filter = str(options.get("topic") or settings.mqtt_topic)
    host = str(options.get("host") or source.endpoint.removeprefix("mqtt://").split(":", 1)[0] or settings.mqtt_host)
    port = int(options.get("port") or (source.endpoint.rsplit(":", 1)[-1] if ":" in source.endpoint else settings.mqtt_port))
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
            mark_source(source.connection_id, source.source_protocol, source.site_id, "connected")
            client.subscribe(topic_filter, qos=int(options.get("qos", settings.mqtt_qos)))
        else:
            mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(reason_code))
            adapter_errors.labels(protocol="mqtt").inc()

    def on_message(_client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        if sparkplug_mode:
            try:
                from services.edge_ingest.mqtt_sparkplug_b import decode_binary_payload, lifecycle_event, parse_lifecycle_topic

                lifecycle = parse_lifecycle_topic(message.topic)
                if lifecycle:
                    mark_source(source.connection_id, source.source_protocol, source.site_id, lifecycle["state"])
                    if lifecycle["state"] == "disconnected":
                        event = lifecycle_event(message.topic, source.site_id, source.source_id or message.topic, lifecycle)
                        mapped, matched, source_field = source.map_event_with_status(event)
                        enqueue_mqtt_message(queue, mapped, publisher, event["source_id"])
                        mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                        return

                events = decode_binary_payload(message.payload, message.topic, source.site_id, source.source_id or message.topic)
                for event in events:
                    mapped, matched, source_field = source.map_event_with_status(event)
                    enqueue_mqtt_message(queue, mapped, publisher, event["source_id"])
                    mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
                mark_source_success(source.connection_id, source.source_protocol, source.site_id)
            except Exception as exc:
                dlq_total.labels(protocol="sparkplug_b").inc()
                publisher.publish_event({"source_protocol": "sparkplug_b", "source_id": source.source_id or message.topic, "asset_id": "", "tag": "", "value": message.payload.hex()[:4096], "quality": "bad", "ts_source": utc_now(), "error": str(exc), "site": source.site_id})
            return
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
        mapped, matched, source_field = source.map_event_with_status(payload)
        enqueue_mqtt_message(queue, mapped, publisher, source_id)
        mark_mapping_result(source.connection_id, source.source_protocol, source.site_id, matched=matched, source_field=source_field)
        mark_source_success(source.connection_id, source.source_protocol, source.site_id)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"edge-ingest-{source.connection_id}")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        credentials = resolve_credentials(source.credential_refs)
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if username or password:
            client.username_pw_set(username, password)
    except CredentialResolutionError as exc:
        mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(exc))
        adapter_errors.labels(protocol="mqtt").inc()
        await queue.put(None)
        await drainer
        return

    # Last Will and Testament: if the adapter disconnects ungracefully the
    # broker publishes the will so downstream consumers learn the adapter is
    # down instead of silently missing data. Only configured when a will topic
    # is supplied; retained on request so late subscribers also see it.
    if settings.mqtt_will_topic:
        client.will_set(
            topic=settings.mqtt_will_topic,
            payload=settings.mqtt_will_payload.encode("utf-8") if settings.mqtt_will_payload else None,
            qos=settings.mqtt_will_qos,
            retain=settings.mqtt_will_retain,
        )
    try:
        credentials = resolve_credentials(source.credential_refs)
    except CredentialResolutionError as exc:
        mark_source(source.connection_id, source.source_protocol, source.site_id, "error", str(exc))
        adapter_errors.labels(protocol="mqtt").inc()
        await queue.put(None)
        await drainer
        return
    mqtt_ca_cert = credentials.get("ca_cert", os.getenv("MQTT_CA_CERT", ""))
    mqtt_certfile = credentials.get("client_cert", os.getenv("MQTT_CERTFILE", ""))
    mqtt_keyfile = credentials.get("client_key", os.getenv("MQTT_KEYFILE", ""))
    if mqtt_ca_cert:
        client.tls_set(
            ca_certs=mqtt_ca_cert,
            certfile=mqtt_certfile or None,
            keyfile=mqtt_keyfile or None,
        )
    try:
        while not stop_event.is_set():
            try:
                client.connect(host, port, keepalive=30)
                client.loop_start()
                await stop_event.wait()
                break
            except Exception:
                mark_source(source.connection_id, source.source_protocol, source.site_id, "reconnecting")
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

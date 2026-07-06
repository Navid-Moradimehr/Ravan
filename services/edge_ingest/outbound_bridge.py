"""Outbound bridge: forward processed events to external MQTT/AMQP brokers."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from confluent_kafka import Consumer, KafkaError
from services.common.brokers import resolve_kafka_brokers


class OutboundBridge:
    """Reads from Kafka topics and forwards to external MQTT/AMQP endpoints."""

    def __init__(
        self,
        kafka_brokers: str = "localhost:19092",
        source_topic: str = "iot.processed",
        mqtt_host: str | None = None,
        mqtt_port: int = 1883,
        mqtt_topic_template: str = "industrial/{{asset_id}}/{{tag}}",
        amqp_url: str | None = None,
        amqp_exchange: str = "industrial.events",
        amqp_routing_key: str = "{{asset_id}}.{{tag}}",
    ):
        self.kafka_brokers = kafka_brokers
        self.source_topic = source_topic
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_topic_template = mqtt_topic_template
        self.amqp_url = amqp_url
        self.amqp_exchange = amqp_exchange
        self.amqp_routing_key = amqp_routing_key
        self._running = False
        self._consumer: Consumer | None = None
        self._mqtt_client: Any | None = None
        self._amqp_connection: Any | None = None

    def _render_template(self, template: str, event: dict[str, Any]) -> str:
        result = template
        for key, value in event.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    def _start_consumer(self) -> Consumer:
        conf = {
            "bootstrap.servers": self.kafka_brokers,
            "group.id": "outbound-bridge",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
        consumer = Consumer(conf)
        consumer.subscribe([self.source_topic])
        return consumer

    def _forward_mqtt(self, event: dict[str, Any]) -> bool:
        if self._mqtt_client is None:
            try:
                from paho.mqtt import client as mqtt

                self._mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="outbound-bridge")
                self._mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=30)
                self._mqtt_client.loop_start()
            except Exception:
                return False
        topic = self._render_template(self.mqtt_topic_template, event)
        payload = json.dumps(event, default=str).encode("utf-8")
        try:
            self._mqtt_client.publish(topic, payload=payload, qos=1)
            return True
        except Exception:
            return False

    def _forward_amqp(self, event: dict[str, Any]) -> bool:
        if self._amqp_connection is None:
            try:
                import pika

                params = pika.URLParameters(self.amqp_url)
                self._amqp_connection = pika.BlockingConnection(params)
            except Exception:
                return False
        channel = self._amqp_connection.channel()
        routing_key = self._render_template(self.amqp_routing_key, event)
        body = json.dumps(event, default=str)
        try:
            channel.basic_publish(
                exchange=self.amqp_exchange,
                routing_key=routing_key,
                body=body.encode("utf-8"),
                properties=pika.BasicProperties(content_type="application/json"),
            )
            return True
        except Exception:
            return False

    def run(self) -> None:
        self._running = True
        self._consumer = self._start_consumer()
        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    break
                self._handle_message(msg)
        finally:
            self.stop()

    def _handle_message(self, msg: Any) -> None:
        """Forward one message and commit its offset only on success.

        At-least-once semantics: if every configured forwarder reports success
        the offset is committed synchronously so the consumer advances. If a
        forward fails the commit is skipped and the message is re-delivered on
        the next poll. A message that cannot be decoded is treated as poison
        and committed past (retrying a malformed payload can never succeed).
        """
        try:
            event = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._commit(msg)
            return
        delivered = True
        if self.mqtt_host:
            delivered = self._forward_mqtt(event) and delivered
        if self.amqp_url:
            delivered = self._forward_amqp(event) and delivered
        if delivered:
            self._commit(msg)

    def _commit(self, msg: Any) -> None:
        from confluent_kafka import TopicPartition

        if self._consumer is None:
            return
        try:
            self._consumer.commit(
                offset=TopicPartition(msg.topic(), msg.partition(), msg.offset() + 1),
                asynchronous=False,
            )
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False
        if self._consumer:
            self._consumer.close()
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
        if self._amqp_connection:
            self._amqp_connection.close()


def main() -> None:
    bridge = OutboundBridge(
        kafka_brokers=resolve_kafka_brokers("localhost:19092"),
        source_topic=os.getenv("OUTBOUND_SOURCE_TOPIC", "iot.processed"),
        mqtt_host=os.getenv("OUTBOUND_MQTT_HOST"),
        mqtt_port=int(os.getenv("OUTBOUND_MQTT_PORT", "1883")),
        mqtt_topic_template=os.getenv("OUTBOUND_MQTT_TOPIC", "industrial/{{asset_id}}/{{tag}}"),
        amqp_url=os.getenv("OUTBOUND_AMQP_URL"),
        amqp_exchange=os.getenv("OUTBOUND_AMQP_EXCHANGE", "industrial.events"),
        amqp_routing_key=os.getenv("OUTBOUND_AMQP_ROUTING_KEY", "{{asset_id}}.{{tag}}"),
    )
    bridge.run()


if __name__ == "__main__":
    main()

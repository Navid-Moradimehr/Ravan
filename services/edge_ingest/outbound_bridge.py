"""Outbound bridge: forward processed events to external MQTT/AMQP brokers."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from confluent_kafka import Consumer, KafkaError


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
            "enable.auto.commit": True,
        }
        consumer = Consumer(conf)
        consumer.subscribe([self.source_topic])
        return consumer

    def _forward_mqtt(self, event: dict[str, Any]) -> None:
        if self._mqtt_client is None:
            try:
                from paho.mqtt import client as mqtt

                self._mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="outbound-bridge")
                self._mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=30)
                self._mqtt_client.loop_start()
            except Exception:
                return
        topic = self._render_template(self.mqtt_topic_template, event)
        payload = json.dumps(event, default=str).encode("utf-8")
        try:
            self._mqtt_client.publish(topic, payload=payload, qos=1)
        except Exception:
            pass

    def _forward_amqp(self, event: dict[str, Any]) -> None:
        if self._amqp_connection is None:
            try:
                import pika

                params = pika.URLParameters(self.amqp_url)
                self._amqp_connection = pika.BlockingConnection(params)
            except Exception:
                return
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
        except Exception:
            pass

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
                try:
                    event = json.loads(msg.value().decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if self.mqtt_host:
                    self._forward_mqtt(event)
                if self.amqp_url:
                    self._forward_amqp(event)
        finally:
            self.stop()

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
        kafka_brokers=os.getenv("REDPANDA_BROKERS", "localhost:19092"),
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

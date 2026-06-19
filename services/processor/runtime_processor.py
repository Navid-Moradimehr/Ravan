from __future__ import annotations

import json
import os
import signal
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from confluent_kafka import Consumer, Producer


def score_event(event: dict[str, Any], temperature_avg: float, vibration_avg: float) -> float:
    score = 0.0
    if float(event.get("temperature_c", 0)) >= 65:
        score += 0.35
    if float(event.get("vibration_mm_s", 0)) >= 7:
        score += 0.35
    if float(event.get("pressure_bar", 0)) >= 8:
        score += 0.2
    if temperature_avg >= 58 or vibration_avg >= 5:
        score += 0.1
    return min(round(score, 2), 1.0)


def normalize_runtime_event(event: dict[str, Any]) -> dict[str, Any]:
    if "device_id" in event:
        return event

    tag = str(event.get("tag", "")).lower()
    value = event.get("value", 0)
    numeric_value = float(value) if isinstance(value, int | float | bool) else 0.0
    normalized = {
        "event_id": event.get("event_id"),
        "device_id": event.get("asset_id", "unknown-asset"),
        "site_id": event.get("site", "demo-site"),
        "timestamp": event.get("ts_source") or event.get("ts_ingest"),
        "source_protocol": event.get("source_protocol", "unknown"),
        "quality": event.get("quality", "unknown"),
        "schema_version": event.get("schema_version", 1),
        "temperature_c": 48.0,
        "vibration_mm_s": 3.0,
        "pressure_bar": 6.2,
    }
    if "temp" in tag:
        normalized["temperature_c"] = numeric_value
    elif "vibration" in tag:
        normalized["vibration_mm_s"] = numeric_value
    elif "pressure" in tag:
        normalized["pressure_bar"] = numeric_value
    return normalized


def severity_for(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.4:
        return "warning"
    return "normal"


def main() -> None:
    brokers = os.getenv("REDPANDA_BROKERS", "localhost:19092")
    input_topic = os.getenv("IOT_TOPIC", "iot.raw")
    output_topic = os.getenv("PROCESSED_TOPIC", "iot.processed")
    running = True
    windows: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=25))

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    consumer = Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": "runtime-iot-processor",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    producer = Producer({"bootstrap.servers": brokers, "client.id": "runtime-iot-processor"})
    consumer.subscribe([input_topic])

    processed = 0
    started_at = time.time()

    try:
        while running:
            message = consumer.poll(1)
            if message is None:
                continue
            if message.error():
                print(f"consumer_error={message.error()}")
                continue

            event = normalize_runtime_event(json.loads(message.value().decode("utf-8")))
            device_window = windows[event["device_id"]]
            device_window.append(event)

            temperature_avg = mean(float(item["temperature_c"]) for item in device_window)
            vibration_avg = mean(float(item["vibration_mm_s"]) for item in device_window)
            anomaly_score = score_event(event, temperature_avg, vibration_avg)
            event["processed_at"] = datetime.now(timezone.utc).isoformat()
            event["window_size"] = len(device_window)
            event["temperature_avg_c"] = round(temperature_avg, 2)
            event["vibration_avg_mm_s"] = round(vibration_avg, 2)
            event["anomaly_score"] = anomaly_score
            event["severity"] = severity_for(anomaly_score)

            producer.produce(output_topic, key=event["device_id"].encode("utf-8"), value=json.dumps(event).encode("utf-8"))
            producer.poll(0)
            processed += 1

            if processed % 100 == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"processed={processed} rate={processed / elapsed:.1f}/sec topic={output_topic}")
    finally:
        consumer.close()
        producer.flush(10)


if __name__ == "__main__":
    main()

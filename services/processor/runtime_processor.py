from __future__ import annotations

import json
import os
import signal
import time
from collections import deque
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from confluent_kafka import Consumer, Producer
from services.common.normalize import normalize_runtime_event

PRUNE_EVERY_N_MESSAGES = 128


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


def severity_for(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.4:
        return "warning"
    return "normal"


def _prune_windows(
    windows: dict[str, deque[dict[str, Any]]],
    last_seen: dict[str, float],
    max_devices: int,
    max_idle_seconds: int,
    now_ts: float,
) -> int:
    removed = 0
    if max_devices <= 0 and max_idle_seconds <= 0:
        return removed

    if max_idle_seconds > 0:
        stale_ids = [device_id for device_id, ts in last_seen.items() if now_ts - ts > max_idle_seconds]
        for device_id in stale_ids:
            windows.pop(device_id, None)
            last_seen.pop(device_id, None)
            removed += 1

    if max_devices > 0 and len(last_seen) > max_devices:
        for device_id, _ in sorted(last_seen.items(), key=lambda item: item[1])[: len(last_seen) - max_devices]:
            windows.pop(device_id, None)
            last_seen.pop(device_id, None)
            removed += 1

    return removed


def main() -> None:
    brokers = os.getenv("REDPANDA_BROKERS", "localhost:19092")
    input_topic = os.getenv("IOT_TOPIC", "iot.raw")
    output_topic = os.getenv("PROCESSED_TOPIC", "iot.processed")
    window_limit = max(1, int(os.getenv("RUNTIME_WINDOW_LIMIT", "25")))
    max_idle_seconds = int(os.getenv("RUNTIME_DEVICE_MAX_IDLE_SECONDS", "0"))
    max_devices = int(os.getenv("RUNTIME_MAX_ACTIVE_DEVICES", "0"))
    running = True
    windows: dict[str, deque[dict[str, Any]]] = {}
    window_last_seen: dict[str, float] = {}

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
            device_id = event["device_id"]
            now_ts = time.time()
            device_window = windows.get(device_id)
            if device_window is None:
                device_window = deque(maxlen=window_limit)
                windows[device_id] = device_window

            window_last_seen[device_id] = now_ts
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

            if processed % PRUNE_EVERY_N_MESSAGES == 0 and (max_devices > 0 or max_idle_seconds > 0):
                removed_windows = _prune_windows(windows, window_last_seen, max_devices, max_idle_seconds, now_ts)
                if removed_windows:
                    print(f"pruned_windows={removed_windows} active_devices={len(windows)}")

            if processed % 100 == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"processed={processed} rate={processed / elapsed:.1f}/sec topic={output_topic}")
    finally:
        consumer.close()
        producer.flush(10)


if __name__ == "__main__":
    main()

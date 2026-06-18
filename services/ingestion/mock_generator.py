from __future__ import annotations

import json
import os
import random
import signal
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from confluent_kafka import Producer


@dataclass(frozen=True)
class SensorEvent:
    event_id: str
    device_id: str
    site_id: str
    timestamp: str
    temperature_c: float
    vibration_mm_s: float
    pressure_bar: float
    schema_version: int = 1


def env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return int(raw_value) if raw_value else default


def build_event(device_count: int) -> SensorEvent:
    device_number = random.randint(1, device_count)
    is_anomalous = random.random() < 0.03

    return SensorEvent(
        event_id=str(uuid.uuid4()),
        device_id=f"device-{device_number:03d}",
        site_id=f"site-{random.randint(1, 4):02d}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        temperature_c=round(random.gauss(72 if is_anomalous else 48, 5), 2),
        vibration_mm_s=round(random.gauss(12 if is_anomalous else 3, 1.2), 2),
        pressure_bar=round(random.gauss(8.8 if is_anomalous else 6.2, 0.4), 2),
    )


def main() -> None:
    brokers = os.getenv("REDPANDA_BROKERS", "localhost:19092")
    topic = os.getenv("IOT_TOPIC", "iot.raw")
    rate_per_second = env_int("MOCK_RATE_PER_SECOND", 100)
    device_count = env_int("MOCK_DEVICE_COUNT", 50)
    delay = 1 / max(rate_per_second, 1)
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    producer = Producer({"bootstrap.servers": brokers, "client.id": "mock-iot-generator"})
    produced = 0
    started_at = time.time()

    while running:
        event = build_event(device_count)
        payload = json.dumps(asdict(event), separators=(",", ":")).encode("utf-8")
        producer.produce(topic, key=event.device_id.encode("utf-8"), value=payload)
        producer.poll(0)
        produced += 1

        if produced % rate_per_second == 0:
            elapsed = max(time.time() - started_at, 0.001)
            print(f"produced={produced} rate={produced / elapsed:.1f}/sec topic={topic}")

        time.sleep(delay)

    producer.flush(10)


if __name__ == "__main__":
    main()

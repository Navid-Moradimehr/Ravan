"""Deterministic five-minute processed-event stream for AI reporting validation."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brokers", default="localhost:19092")
    parser.add_argument("--topic", default="iot.processed")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--warning-seconds", type=int, default=20)
    parser.add_argument("--rate", type=float, default=3.0)
    args = parser.parse_args()
    producer = Producer({"bootstrap.servers": args.brokers, "client.id": "ai-warning-soak"})
    sources = [("plant-a", "Pump-01", "Vibration"), ("plant-a", "Pump-02", "Temperature"), ("plant-b", "Motor-01", "Current")]
    interval = 1.0 / max(args.rate, 0.1)
    started = time.monotonic()
    sent = 0
    while time.monotonic() - started < args.seconds:
        elapsed = int(time.monotonic() - started)
        for index, (site, asset, tag) in enumerate(sources):
            # Include the boundary sample so a 20-second condition has an event
            # at t=20 rather than ending at t=19.
            warning = index == 0 and elapsed <= args.warning_seconds
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "processed_event",
                "event_version": 1,
                "source_protocol": ("opcua", "mqtt", "modbus")[index],
                "source_id": f"{site}/{asset}",
                "site_id": site,
                "asset_id": asset,
                "tag": tag,
                "value": 14.0 if warning else 4.0 + index,
                "unit": "mm/s" if tag == "Vibration" else "c" if tag == "Temperature" else "A",
                "quality": "good",
                "severity": "warning" if warning else "normal",
                "anomaly_score": 0.92 if warning else 0.04,
                "replay_source": "",
                "time": datetime.now(timezone.utc).isoformat(),
            }
            producer.produce(args.topic, key=f"{site}/{asset}/{tag}".encode(), value=json.dumps(event).encode())
            sent += 1
        producer.poll(0)
        time.sleep(interval)
    producer.flush(30)
    print(json.dumps({"sent": sent, "seconds": args.seconds, "warning_seconds": args.warning_seconds, "topic": args.topic}))


if __name__ == "__main__":
    main()

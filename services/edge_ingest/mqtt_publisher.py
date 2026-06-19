from __future__ import annotations

import json
import os
import random
import signal
import time

from paho.mqtt import client as mqtt

from services.edge_ingest.model import IndustrialEvent, to_json_bytes, utc_now


def main() -> None:
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    rate = int(os.getenv("MQTT_RATE_PER_SECOND", "25"))
    max_events = int(os.getenv("MQTT_MAX_EVENTS", "0"))
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="factory-mqtt-sim")
    client.connect(host, port, keepalive=30)
    client.loop_start()

    tags = [("Temperature", "c", 48, 6), ("Vibration", "mm/s", 3, 1), ("Pressure", "bar", 6.2, 0.5)]
    produced = 0
    delay = 1 / max(rate, 1)
    while running:
        asset = f"Pump-{random.randint(1, 8):02d}"
        tag, unit, center, sigma = random.choice(tags)
        event = IndustrialEvent(
            source_protocol="mqtt",
            source_id=f"factory/line-01/{asset}/{tag}",
            asset_id=asset,
            tag=tag,
            value=round(random.gauss(center, sigma), 2),
            quality="bad" if random.random() < 0.01 else "good",
            unit=unit,
            ts_source=utc_now(),
        )
        client.publish(f"factory/line-01/{asset}/{tag}", payload=to_json_bytes(event), qos=1)
        produced += 1
        if max_events and produced >= max_events:
            running = False
        time.sleep(delay)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()

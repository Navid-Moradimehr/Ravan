from __future__ import annotations

import json
import os
import random
import signal
import time

from paho.mqtt import client as mqtt

from services.edge_ingest.model import IndustrialEvent, to_json_bytes, utc_now
from services.scenarios.engine import ScenarioState, apply_scenario, advance_scenario, load_scenario_from_env


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
    scenario_state = load_scenario_from_env()
    while running:
        asset = f"Pump-{random.randint(1, 8):02d}"
        tag, unit, center, sigma = random.choice(tags)
        base_value = random.gauss(center, sigma)
        value = apply_scenario(base_value, scenario_state)
        label = scenario_state.label()
        event = IndustrialEvent(
            source_protocol="mqtt",
            source_id=f"factory/line-01/{asset}/{tag}",
            asset_id=asset,
            tag=tag,
            value=round(value, 2),
            quality="bad" if label["ground_truth_severity"] == "critical" else ("uncertain" if label["ground_truth_severity"] == "warning" else "good"),
            unit=unit,
            ts_source=utc_now(),
        )
        client.publish(f"factory/line-01/{asset}/{tag}", payload=to_json_bytes(event), qos=1)
        produced += 1
        advance_scenario(scenario_state)
        if max_events and produced >= max_events:
            running = False
        time.sleep(delay)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()

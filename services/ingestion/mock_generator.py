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
from services.common.brokers import resolve_kafka_brokers
from services.scenarios.engine import ScenarioState, apply_scenario, advance_scenario, load_scenario_from_env


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
    fault_type: str = "normal"
    scenario_id: str = "sc-000"
    ground_truth_severity: str = "normal"
    step: int = 0


def env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return int(raw_value) if raw_value else default


def build_event(device_count: int, scenario_state: ScenarioState) -> SensorEvent:
    device_number = random.randint(1, device_count)
    base_temp = random.gauss(48, 5)
    base_vib = random.gauss(3, 1.2)
    base_press = random.gauss(6.2, 0.4)

    temp = apply_scenario(base_temp, scenario_state)
    vib = apply_scenario(base_vib, scenario_state)
    press = apply_scenario(base_press, scenario_state)

    label = scenario_state.label()

    return SensorEvent(
        event_id=str(uuid.uuid4()),
        device_id=f"device-{device_number:03d}",
        site_id=f"site-{random.randint(1, 4):02d}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        temperature_c=round(temp, 2),
        vibration_mm_s=round(vib, 2),
        pressure_bar=round(press, 2),
        fault_type=label["fault_type"],
        scenario_id=label["scenario_id"],
        ground_truth_severity=label["ground_truth_severity"],
        step=label["step"],
    )


def main() -> None:
    brokers = resolve_kafka_brokers("localhost:19092")
    topic = os.getenv("IOT_TOPIC", "iot.raw")
    rate_per_second = env_int("MOCK_RATE_PER_SECOND", 100)
    device_count = env_int("MOCK_DEVICE_COUNT", 50)
    max_events = env_int("MOCK_MAX_EVENTS", 0)
    delay = 1 / max(rate_per_second, 1)
    running = True
    scenario_state = load_scenario_from_env()

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    producer = Producer({"bootstrap.servers": brokers, "client.id": "mock-iot-generator"})
    produced = 0
    started_at = time.time()

    while running:
        event = build_event(device_count, scenario_state)
        payload = json.dumps(asdict(event), separators=(",", ":")).encode("utf-8")
        producer.produce(topic, key=event.device_id.encode("utf-8"), value=payload)
        producer.poll(0)
        produced += 1
        advance_scenario(scenario_state)

        if produced % rate_per_second == 0:
            elapsed = max(time.time() - started_at, 0.001)
            print(f"produced={produced} rate={produced / elapsed:.1f}/sec topic={topic}")
            print(f"scenario={scenario_state.scenario_type.value} step={scenario_state.step}")

        if max_events and produced >= max_events:
            running = False

        time.sleep(delay)

    producer.flush(10)


if __name__ == "__main__":
    main()

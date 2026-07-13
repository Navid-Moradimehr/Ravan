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


class GeneratorStats:
    """Delivery accounting for live soak runs.

    The generator is also used interactively, so this remains an optional
    sidecar report rather than part of the industrial event contract.
    """

    def __init__(self) -> None:
        self.attempted = 0
        self.acknowledged = 0
        self.failed = 0
        self.queue_full = 0
        self.started_at = time.time()
        self.finished_at = self.started_at

    def delivery_callback(self, error: object, _message: object) -> None:
        if error is None:
            self.acknowledged += 1
        else:
            self.failed += 1

    def report(self, *, site_id: str, topic: str, target_rate: int) -> dict[str, object]:
        elapsed = max(self.finished_at - self.started_at, 0.001)
        return {
            "site_id": site_id,
            "topic": topic,
            "target_rate_per_second": target_rate,
            "attempted": self.attempted,
            "acknowledged": self.acknowledged,
            "failed": self.failed,
            "queue_full": self.queue_full,
            "elapsed_seconds": round(elapsed, 3),
            "effective_attempt_rate": round(self.attempted / elapsed, 3),
            "effective_ack_rate": round(self.acknowledged / elapsed, 3),
        }


def env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return int(raw_value) if raw_value else default


def build_event(device_count: int, scenario_state: ScenarioState, *, site_id: str | None = None) -> SensorEvent:
    device_number = random.randint(1, device_count)
    base_temp = random.gauss(48, 5)
    base_vib = random.gauss(3, 1.2)
    base_press = random.gauss(6.2, 0.4)

    temp = apply_scenario(base_temp, scenario_state)
    vib = apply_scenario(base_vib, scenario_state)
    press = apply_scenario(base_press, scenario_state)

    label = scenario_state.label()
    resolved_site_id = site_id or f"site-{random.randint(1, 4):02d}"

    return SensorEvent(
        event_id=str(uuid.uuid4()),
        device_id=f"device-{device_number:03d}",
        site_id=resolved_site_id,
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
    site_id = os.getenv("MOCK_SITE_ID", "").strip() or None
    delay = 1 / max(rate_per_second, 1)
    running = True
    scenario_state = load_scenario_from_env()

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    producer = Producer(
        {
            "bootstrap.servers": brokers,
            "client.id": "mock-iot-generator",
            "acks": "all",
            "enable.idempotence": True,
        }
    )
    stats = GeneratorStats()
    report_path = os.getenv("MOCK_REPORT_PATH", "").strip()
    produced = 0
    next_emit = time.monotonic()

    while running:
        event = build_event(device_count, scenario_state, site_id=site_id)
        payload = json.dumps(asdict(event), separators=(",", ":")).encode("utf-8")
        try:
            producer.produce(
                topic,
                key=event.device_id.encode("utf-8"),
                value=payload,
                callback=stats.delivery_callback,
            )
            stats.attempted += 1
        except BufferError:
            stats.queue_full += 1
            producer.poll(0.1)
            continue
        producer.poll(0)
        produced += 1
        advance_scenario(scenario_state)

        if produced % rate_per_second == 0:
            elapsed = max(time.time() - stats.started_at, 0.001)
            print(f"produced={produced} rate={produced / elapsed:.1f}/sec topic={topic}")
            print(f"scenario={scenario_state.scenario_type.value} step={scenario_state.step}")

        if max_events and produced >= max_events:
            running = False

        next_emit += delay
        remaining = next_emit - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        else:
            # Reset instead of accumulating an increasingly late schedule.
            next_emit = time.monotonic()

    producer.flush(10)
    stats.finished_at = time.time()
    report = stats.report(site_id=site_id or "random-site", topic=topic, target_rate=rate_per_second)
    report["produced"] = produced
    print("generator_report=" + json.dumps(report, separators=(",", ":")))
    if report_path:
        with open(report_path, "w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2)


if __name__ == "__main__":
    main()

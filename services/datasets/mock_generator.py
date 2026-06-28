"""Mock industrial data generator for testing without external datasets.

Generates realistic sensor data with configurable scenarios.
Can be used standalone or as a library for tests.
"""
from __future__ import annotations

import csv
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from confluent_kafka import Producer

from services.edge_ingest.model import utc_now
from services.scenarios.engine import ScenarioState, ScenarioType, apply_scenario, advance_scenario, load_scenario_from_env


@dataclass
class AssetConfig:
    asset_id: str
    tag: str
    unit: str
    base_value: float
    variance: float
    min: float = 0.0
    max: float = 100.0


@dataclass
class MockGeneratorConfig:
    assets: list[AssetConfig] = field(default_factory=list)
    scenario: ScenarioState = field(default_factory=lambda: ScenarioState(ScenarioType.NORMAL))
    rate_per_second: int = 10
    loop: bool = True
    max_events: int = 0


# Predefined asset configurations for common industrial equipment
PUMP_ASSETS = [
    AssetConfig("Pump-01", "Temperature", "c", 55.0, 5.0, 0.0, 120.0),
    AssetConfig("Pump-01", "Vibration", "mm/s", 3.5, 1.0, 0.0, 20.0),
    AssetConfig("Pump-01", "Pressure", "bar", 6.0, 1.5, 0.0, 15.0),
    AssetConfig("Pump-02", "Temperature", "c", 52.0, 4.5, 0.0, 120.0),
    AssetConfig("Pump-02", "Vibration", "mm/s", 3.2, 0.8, 0.0, 20.0),
    AssetConfig("Pump-02", "Pressure", "bar", 5.8, 1.2, 0.0, 15.0),
    AssetConfig("Pump-03", "Temperature", "c", 58.0, 6.0, 0.0, 120.0),
    AssetConfig("Pump-03", "Vibration", "mm/s", 4.0, 1.2, 0.0, 20.0),
    AssetConfig("Pump-03", "Pressure", "bar", 6.2, 1.8, 0.0, 15.0),
]

MOTOR_ASSETS = [
    AssetConfig("Motor-01", "Current", "A", 12.0, 2.0, 0.0, 50.0),
    AssetConfig("Motor-01", "Voltage", "V", 380.0, 5.0, 300.0, 450.0),
    AssetConfig("Motor-01", "RPM", "rpm", 1750.0, 50.0, 0.0, 3000.0),
    AssetConfig("Motor-01", "Temperature", "c", 65.0, 8.0, 0.0, 150.0),
    AssetConfig("Motor-02", "Current", "A", 11.5, 1.8, 0.0, 50.0),
    AssetConfig("Motor-02", "Voltage", "V", 380.0, 4.0, 300.0, 450.0),
    AssetConfig("Motor-02", "RPM", "rpm", 1720.0, 45.0, 0.0, 3000.0),
    AssetConfig("Motor-02", "Temperature", "c", 62.0, 7.0, 0.0, 150.0),
]

TURBINE_ASSETS = [
    AssetConfig("Turbine-01", "Power", "MW", 2.5, 0.3, 0.0, 5.0),
    AssetConfig("Turbine-01", "RPM", "rpm", 3600.0, 100.0, 0.0, 4000.0),
    AssetConfig("Turbine-01", "InletTemp", "c", 450.0, 20.0, 0.0, 600.0),
    AssetConfig("Turbine-01", "OutletTemp", "c", 280.0, 15.0, 0.0, 400.0),
    AssetConfig("Turbine-01", "Vibration", "mm/s", 2.8, 0.5, 0.0, 10.0),
]

ALL_PRESETS = {
    "pump": PUMP_ASSETS,
    "motor": MOTOR_ASSETS,
    "turbine": TURBINE_ASSETS,
    "all": PUMP_ASSETS + MOTOR_ASSETS + TURBINE_ASSETS,
}


def generate_value(asset: AssetConfig, scenario: ScenarioState) -> float:
    """Generate a realistic sensor value with scenario applied."""
    base = asset.base_value + random.gauss(0, asset.variance)
    value = apply_scenario(base, scenario)
    # Clamp to physical limits
    value = max(asset.min, min(asset.max, value))
    return round(value, 3)


def generate_event(asset: AssetConfig, scenario: ScenarioState) -> dict[str, Any]:
    """Generate a complete IndustrialEvent dict."""
    value = generate_value(asset, scenario)
    quality = "good"
    if value >= asset.max * 0.95 or value <= asset.min * 1.05:
        quality = "bad"
    elif value >= asset.max * 0.85 or value <= asset.min * 1.15:
        quality = "uncertain"

    return {
        "event_id": f"evt-{random.randint(100000, 999999)}",
        "source_protocol": "mock",
        "source_id": f"mock/{asset.asset_id}",
        "asset_id": asset.asset_id,
        "tag": asset.tag,
        "value": value,
        "quality": quality,
        "unit": asset.unit,
        "site": "demo-site",
        "line": "line-01",
        "ts_source": utc_now(),
        "schema_version": 1,
        **scenario.label(),
    }


def generate_events(config: MockGeneratorConfig) -> Iterator[dict[str, Any]]:
    """Generate a stream of mock events."""
    produced = 0
    while config.max_events == 0 or produced < config.max_events:
        for asset in config.assets:
            event = generate_event(asset, config.scenario)
            yield event
            produced += 1
            if config.max_events and produced >= config.max_events:
                return
        advance_scenario(config.scenario)
        time.sleep(1 / max(config.rate_per_second, 1))


def generate_csv(config: MockGeneratorConfig, output_path: Path, num_rows: int = 1000) -> None:
    """Generate a CSV file with mock data for replay."""
    events = []
    for _ in range(num_rows):
        for asset in config.assets:
            event = generate_event(asset, config.scenario)
            events.append(event)
            advance_scenario(config.scenario)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        if events:
            writer = csv.DictWriter(f, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
    print(f"Generated {len(events)} events to {output_path}")


def replay_to_kafka(
    config: MockGeneratorConfig,
    topic: str = "industrial.normalized",
    brokers: str = None,
) -> None:
    """Stream mock events to Kafka/Redpanda."""
    if brokers is None:
        brokers = os.getenv("REDPANDA_BROKERS", "localhost:19092")

    producer = Producer({"bootstrap.servers": brokers, "client.id": "mock-generator"})
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    import signal
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    produced = 0
    started_at = time.time()

    for event in generate_events(config):
        if not running:
            break
        payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
        producer.produce(topic, key=event["asset_id"].encode("utf-8"), value=payload)
        producer.poll(0)
        produced += 1

        if produced % config.rate_per_second == 0:
            elapsed = max(time.time() - started_at, 0.001)
            print(f"produced={produced} rate={produced / elapsed:.1f}/sec topic={topic}")

    producer.flush(10)
    print(f"mock_replay_done produced={produced} topic={topic}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate mock industrial data")
    parser.add_argument("--preset", choices=list(ALL_PRESETS.keys()), default="pump",
                        help="Asset preset to use")
    parser.add_argument("--scenario", choices=[s.value for s in ScenarioType], default="normal",
                        help="Scenario type to inject")
    parser.add_argument("--rate", type=int, default=10, help="Events per second")
    parser.add_argument("--max-events", type=int, default=0, help="Max events (0=unlimited)")
    parser.add_argument("--csv", type=Path, help="Output CSV file instead of Kafka")
    parser.add_argument("--csv-rows", type=int, default=1000, help="Rows per asset for CSV")
    parser.add_argument("--topic", default="industrial.normalized", help="Kafka topic")
    parser.add_argument("--brokers", default=os.getenv("REDPANDA_BROKERS", "localhost:19092"),
                        help="Kafka brokers")
    args = parser.parse_args()

    scenario = ScenarioState(
        scenario_type=ScenarioType(args.scenario),
        scenario_id=f"sc-{random.randint(100, 999):03d}",
    )
    config = MockGeneratorConfig(
        assets=ALL_PRESETS[args.preset],
        scenario=scenario,
        rate_per_second=args.rate,
        max_events=args.max_events,
    )

    if args.csv:
        generate_csv(config, args.csv, args.csv_rows)
    else:
        replay_to_kafka(config, args.topic, args.brokers)


if __name__ == "__main__":
    main()

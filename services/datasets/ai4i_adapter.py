from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import time
from pathlib import Path
from typing import Any

try:
    from confluent_kafka import Producer
    HAS_KAFKA = True
except Exception:  # pragma: no cover - optional runtime dependency
    Producer = Any  # type: ignore[assignment]
    HAS_KAFKA = False

from services.common.brokers import resolve_kafka_brokers
from services.edge_ingest.model import to_json_bytes, utc_now


def build_producer(brokers: str) -> Producer:
    if not HAS_KAFKA:
        raise RuntimeError("confluent_kafka is required for live AI4I replay")
    return Producer({"bootstrap.servers": brokers, "client.id": "ai4i-replayer"})


def read_ai4i_rows(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def map_ai4i_row(row: dict[str, str], machine_id: str) -> dict[str, Any]:
    """Map one AI4I row to a set of IndustrialEvent-shaped dicts.

    AI4I columns (typical):
        UDI, Product ID, Type, Air temperature [K],
        Process temperature [K], Rotational speed [rpm], Torque [Nm],
        Tool wear [min], Machine failure, TWF, HDF, PWF, OSF, RNF
    """
    events: list[dict[str, Any]] = []
    base = {
        "source_protocol": "dataset",
        "source_id": f"ai4i/{machine_id}",
        "asset_id": machine_id,
        "site": "demo-site",
        "line": "line-01",
        "ts_source": utc_now(),
        "schema_version": 1,
    }

    # Map known columns to tags
    tag_map = {
        "Air temperature [K]": ("AirTemperature", "K"),
        "Process temperature [K]": ("ProcessTemperature", "K"),
        "Rotational speed [rpm]": ("RotationalSpeed", "rpm"),
        "Torque [Nm]": ("Torque", "Nm"),
        "Tool wear [min]": ("ToolWear", "min"),
    }

    for csv_col, (tag, unit) in tag_map.items():
        if csv_col in row:
            try:
                value = float(row[csv_col])
            except ValueError:
                value = 0.0
            quality = "good"
            # Mark as uncertain if machine failure flag is set
            if row.get("Machine failure", "0") == "1":
                quality = "bad"
            events.append({
                **base,
                "event_id": "",
                "tag": tag,
                "value": value,
                "quality": quality,
                "unit": unit,
            })

    # Add failure indicator as a synthetic tag if failure occurred
    if row.get("Machine failure", "0") == "1":
        failure_tags = []
        for flag_col, label in (
            ("TWF", "ToolWearFailure"),
            ("HDF", "HeatDissipationFailure"),
            ("PWF", "PowerFailure"),
            ("OSF", "OverstrainFailure"),
            ("RNF", "RandomFailure"),
        ):
            if row.get(flag_col, "0") == "1":
                failure_tags.append(label)
        events.append({
            **base,
            "event_id": "",
            "tag": "MachineFailure",
            "value": 1.0,
            "quality": "bad",
            "unit": "",
        })

    return events


def replay_ai4i(
    csv_path: Path,
    topic: str,
    brokers: str,
    rate_per_second: int,
    loop: bool,
    max_events: int,
) -> None:
    producer = build_producer(brokers)
    rows = read_ai4i_rows(csv_path)
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    delay = 1 / max(rate_per_second, 1)
    produced = 0
    started_at = time.time()

    while running:
        for index, row in enumerate(rows):
            if not running:
                break
            machine_id = f"M-{row.get('UDI', index)}"
            events = map_ai4i_row(row, machine_id)
            for event in events:
                payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
                producer.produce(topic, key=machine_id.encode("utf-8"), value=payload)
                producer.poll(0)
                produced += 1

                if max_events and produced >= max_events:
                    running = False
                    break

            if produced % rate_per_second == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"produced={produced} rate={produced / elapsed:.1f}/sec topic={topic}")

            if not running:
                break

            time.sleep(delay)

        if not loop:
            break

    producer.flush(10)
    print(f"ai4i_replay_done produced={produced} topic={topic}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay AI4I 2020 predictive maintenance dataset into Kafka")
    parser.add_argument("--csv", required=True, type=Path, help="Path to AI4I CSV file")
    parser.add_argument("--topic", default="industrial.normalized", help="Target Kafka topic")
    parser.add_argument("--brokers", default=resolve_kafka_brokers("localhost:19092"), help="Kafka brokers")
    parser.add_argument("--rate", type=int, default=25, help="Messages per second")
    parser.add_argument("--loop", action="store_true", help="Loop the dataset indefinitely")
    parser.add_argument("--max-events", type=int, default=0, help="Max events to produce (0 = unlimited)")
    args = parser.parse_args()

    replay_ai4i(
        csv_path=args.csv,
        topic=args.topic,
        brokers=args.brokers,
        rate_per_second=args.rate,
        loop=args.loop,
        max_events=args.max_events,
    )


if __name__ == "__main__":
    main()

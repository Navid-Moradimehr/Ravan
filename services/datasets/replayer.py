from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

try:
    from confluent_kafka import Producer
    HAS_KAFKA = True
except Exception:  # pragma: no cover - optional runtime dependency
    Producer = Any  # type: ignore[assignment]
    HAS_KAFKA = False

from services.common.brokers import resolve_kafka_brokers
from services.edge_ingest.model import IndustrialEvent, to_json_bytes, utc_now
from services.common.stream_scope import stream_partition_key


@dataclass(frozen=True)
class ReplayConfig:
    csv_path: Path
    topic: str
    brokers: str
    rate_per_second: int
    loop: bool
    timestamp_column: str | None
    mapping: dict[str, str]
    max_events: int = 0
    time_travel_start: datetime | None = None
    time_travel_end: datetime | None = None


def build_producer(brokers: str) -> Producer:
    if not HAS_KAFKA:
        raise RuntimeError("confluent_kafka is required for live dataset replay")
    return Producer({"bootstrap.servers": brokers, "client.id": "dataset-replayer"})


def read_csv_rows(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def filter_rows_by_time(
    rows: Iterator[dict[str, Any]],
    timestamp_column: str,
    start: datetime | None,
    end: datetime | None,
) -> Iterator[dict[str, Any]]:
    for row in rows:
        ts_raw = row.get(timestamp_column)
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (start is None or ts >= start) and (end is None or ts <= end):
            yield row


def map_row_to_event(
    row: dict[str, str],
    mapping: dict[str, str],
) -> dict[str, Any]:
    """Map CSV columns to IndustrialEvent fields using the provided mapping."""
    event: dict[str, Any] = {
        "event_id": "",
        "source_protocol": "dataset",
        "source_id": "",
        "asset_id": "",
        "tag": "",
        "value": 0,
        "quality": "good",
        "unit": "",
        "site": "demo-site",
        "line": "line-01",
        "ts_source": "",
        "schema_version": 1,
        "replay_offset_ms": 0,
        "replay_source": "time_travel",
    }
    for csv_col, event_field in mapping.items():
        raw = row.get(csv_col, "")
        if event_field == "value":
            try:
                event[event_field] = float(raw)
            except ValueError:
                event[event_field] = 0.0
        elif event_field in ("schema_version", "step"):
            try:
                event[event_field] = int(raw)
            except ValueError:
                event[event_field] = 0
        else:
            event[event_field] = raw
    if not event["ts_source"]:
        event["ts_source"] = utc_now()
    return event


def replay(config: ReplayConfig) -> None:
    producer = build_producer(config.brokers)
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    delay = 1 / max(config.rate_per_second, 1)
    produced = 0
    started_at = time.time()
    # Time-travel: filter rows by timestamp window
    rows = read_csv_rows(config.csv_path)
    if config.timestamp_column and (config.time_travel_start or config.time_travel_end):
        rows = filter_rows_by_time(rows, config.timestamp_column, config.time_travel_start, config.time_travel_end)

    while running:
        for row in rows:
            if not running:
                break
            event_dict = map_row_to_event(row, config.mapping)
            if config.timestamp_column and config.timestamp_column in row:
                event_dict["ts_source"] = row[config.timestamp_column]
            payload = json.dumps(event_dict, separators=(",", ":")).encode("utf-8")
            producer.produce(config.topic, key=stream_partition_key(event_dict), value=payload)
            producer.poll(0)
            produced += 1

            if produced % config.rate_per_second == 0:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"produced={produced} rate={produced / elapsed:.1f}/sec topic={config.topic}")

            if config.max_events and produced >= config.max_events:
                running = False
                break

            time.sleep(delay)

        if not config.loop:
            break

    producer.flush(10)
    print(f"dataset_replay_done produced={produced} topic={config.topic}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay industrial dataset CSV into Kafka")
    parser.add_argument("--csv", required=True, type=Path, help="Path to CSV file")
    parser.add_argument("--topic", default="industrial.normalized", help="Target Kafka topic")
    parser.add_argument("--brokers", default=resolve_kafka_brokers("localhost:19092"), help="Kafka brokers")
    parser.add_argument("--rate", type=int, default=10, help="Messages per second")
    parser.add_argument("--loop", action="store_true", help="Loop the dataset indefinitely")
    parser.add_argument("--timestamp-col", default=None, help="Column to use as ts_source")
    parser.add_argument("--max-events", type=int, default=0, help="Max events to produce (0 = unlimited)")
    parser.add_argument("--time-travel-start", default=None, help="ISO timestamp to start replay from")
    parser.add_argument("--time-travel-end", default=None, help="ISO timestamp to end replay at")
    parser.add_argument(
        "--mapping",
        default=(
            "asset_id=asset_id,tag=tag,value=value,source_protocol=source_protocol,"
            "source_id=source_id,quality=quality,unit=unit,site=site,line=line,"
            "ts_source=ts_source,schema_version=schema_version,fault_type=fault_type,"
            "scenario_id=scenario_id,ground_truth_severity=ground_truth_severity,step=step"
        ),
        help="Comma-separated CSV-col=event-field mappings",
    )
    args = parser.parse_args()

    mapping: dict[str, str] = {}
    for pair in args.mapping.split(","):
        csv_col, event_field = pair.split("=", 1)
        mapping[csv_col.strip()] = event_field.strip()

    config = ReplayConfig(
        csv_path=args.csv,
        topic=args.topic,
        brokers=args.brokers,
        rate_per_second=args.rate,
        loop=args.loop,
        timestamp_column=args.timestamp_col,
        mapping=mapping,
        max_events=args.max_events,
        time_travel_start=datetime.fromisoformat(args.time_travel_start) if args.time_travel_start else None,
        time_travel_end=datetime.fromisoformat(args.time_travel_end) if args.time_travel_end else None,
    )
    replay(config)


if __name__ == "__main__":
    main()

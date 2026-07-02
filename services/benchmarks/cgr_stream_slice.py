from __future__ import annotations

import argparse
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path
from statistics import mean
from typing import Any

from services.common.normalize import normalize_runtime_event
from services.common.stream_scope import stream_partition_key
from services.datasets.replayer import map_row_to_event, read_csv_rows
from services.edge_ingest.model import to_json_bytes, validate_event
from services.processor.scoring import score_event, severity_for


DEFAULT_MAPPING: dict[str, str] = {
    "asset_id": "asset_id",
    "tag": "tag",
    "value": "value",
    "source_protocol": "source_protocol",
    "source_id": "source_id",
    "quality": "quality",
    "unit": "unit",
    "site": "site",
    "line": "line",
    "ts_source": "ts_source",
    "schema_version": "schema_version",
    "fault_type": "fault_type",
    "scenario_id": "scenario_id",
    "ground_truth_severity": "ground_truth_severity",
    "step": "step",
}


@dataclass(frozen=True)
class StreamingSliceBenchmarkResult:
    csv_path: str
    events: int
    invalid_events: int
    batches: int
    batch_size: int
    window_limit: int
    elapsed_seconds: float
    events_per_second: float
    serialized_bytes: int
    raw_bytes: int
    normalized_bytes: int
    processed_bytes: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    rows = list(read_csv_rows(csv_path))
    if not rows:
        raise ValueError(f"benchmark input is empty: {csv_path}")
    return rows


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 4)
    ordered = sorted(values)
    rank = (percentile / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    value = ordered[lower] * (1.0 - weight) + ordered[upper] * weight
    return round(value, 4)


def run_benchmark(
    csv_path: Path,
    target_events: int = 100_000,
    batch_size: int = 256,
    warmup_events: int = 1_000,
    window_limit: int = 25,
) -> StreamingSliceBenchmarkResult:
    rows = _load_rows(csv_path)
    total_iterations = target_events + warmup_events
    events = 0
    invalid_events = 0
    raw_bytes = 0
    normalized_bytes = 0
    processed_bytes = 0
    batch_count = 0
    latencies_ms: list[float] = []
    windows: dict[str, deque[dict[str, Any]]] = {}

    start = time.perf_counter()
    rows_iter = cycle(rows)

    for index in range(total_iterations):
        row = next(rows_iter)
        started = time.perf_counter()
        mapped = map_row_to_event(row, DEFAULT_MAPPING)
        event, dlq = validate_event(mapped)
        if event is None or dlq is not None:
            invalid_events += 1
            continue

        raw_payload = to_json_bytes(mapped)
        normalized = normalize_runtime_event(event.model_dump(mode="json"))
        key = stream_partition_key(event)

        device_window = windows.get(normalized["device_id"])
        if device_window is None:
            device_window = deque(maxlen=window_limit)
            windows[normalized["device_id"]] = device_window

        device_window.append(normalized)
        temperature_avg = mean(float(item["temperature_c"]) for item in device_window)
        vibration_avg = mean(float(item["vibration_mm_s"]) for item in device_window)
        anomaly_score = score_event(normalized, temperature_avg, vibration_avg, detector=None)
        processed = dict(normalized)
        processed["processed_at"] = datetime.now(timezone.utc).isoformat()
        processed["window_size"] = len(device_window)
        processed["temperature_avg_c"] = round(temperature_avg, 2)
        processed["vibration_avg_mm_s"] = round(vibration_avg, 2)
        processed["anomaly_score"] = anomaly_score
        processed["severity"] = severity_for(anomaly_score)
        normalized_payload = to_json_bytes(normalized)
        processed_payload = to_json_bytes(processed)

        if index >= warmup_events:
            events += 1
            latencies_ms.append((time.perf_counter() - started) * 1000.0)
            raw_bytes += len(raw_payload)
            normalized_bytes += len(normalized_payload)
            processed_bytes += len(processed_payload)
            if events % batch_size == 0:
                batch_count += 1

    if events and events % batch_size:
        batch_count += 1

    elapsed = max(time.perf_counter() - start, 1e-9)
    return StreamingSliceBenchmarkResult(
        csv_path=str(csv_path),
        events=events,
        invalid_events=invalid_events,
        batches=batch_count,
        batch_size=batch_size,
        window_limit=window_limit,
        elapsed_seconds=round(elapsed, 4),
        events_per_second=round(events / elapsed, 2),
        serialized_bytes=raw_bytes + normalized_bytes + processed_bytes,
        raw_bytes=raw_bytes,
        normalized_bytes=normalized_bytes,
        processed_bytes=processed_bytes,
        latency_p50_ms=_percentile(latencies_ms, 50.0),
        latency_p95_ms=_percentile(latencies_ms, 95.0),
        latency_p99_ms=_percentile(latencies_ms, 99.0),
        latency_max_ms=round(max(latencies_ms), 4) if latencies_ms else 0.0,
    )


def format_result(result: StreamingSliceBenchmarkResult) -> str:
    return "\n".join(
        [
            f"csv={result.csv_path}",
            f"events={result.events}",
            f"invalid_events={result.invalid_events}",
            f"batches={result.batches}",
            f"batch_size={result.batch_size}",
            f"window_limit={result.window_limit}",
            f"elapsed_seconds={result.elapsed_seconds}",
            f"events_per_second={result.events_per_second}",
            f"serialized_bytes={result.serialized_bytes}",
            f"raw_bytes={result.raw_bytes}",
            f"normalized_bytes={result.normalized_bytes}",
            f"processed_bytes={result.processed_bytes}",
            f"latency_p50_ms={result.latency_p50_ms}",
            f"latency_p95_ms={result.latency_p95_ms}",
            f"latency_p99_ms={result.latency_p99_ms}",
            f"latency_max_ms={result.latency_max_ms}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the isolated stream-processing slice used for CGR-style comparisons.")
    parser.add_argument("--csv", type=Path, default=Path("data/benchmarks/industrial_mixed_benchmark.csv"))
    parser.add_argument("--events", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--warmup-events", type=int, default=1_000)
    parser.add_argument("--window-limit", type=int, default=25)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(
        csv_path=args.csv,
        target_events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        window_limit=args.window_limit,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

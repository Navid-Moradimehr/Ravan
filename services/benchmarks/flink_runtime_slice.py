from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path

from services.common.runtime_event import RollingWindowState, RuntimeEventRecord
from services.datasets.replayer import map_row_to_event, read_csv_rows
from services.edge_ingest.model import to_json_bytes, validate_event
from services.processor.runtime_pipeline import build_runtime_event_payload


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
class StageBenchmarkResult:
    name: str
    operations: int
    elapsed_seconds: float
    events_per_second: float
    avg_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float


@dataclass(frozen=True)
class FlinkRuntimeSliceBenchmarkResult:
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
    stage_breakdown: tuple[StageBenchmarkResult, ...] = ()


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


def _stage_result(name: str, durations_ms: list[float]) -> StageBenchmarkResult:
    operations = len(durations_ms)
    total_ms = sum(durations_ms)
    elapsed_seconds = round(total_ms / 1000.0, 6)
    events_per_second = round(operations / elapsed_seconds, 2) if elapsed_seconds > 0 else 0.0
    avg_ms = round(total_ms / operations, 4) if operations else 0.0
    return StageBenchmarkResult(
        name=name,
        operations=operations,
        elapsed_seconds=elapsed_seconds,
        events_per_second=events_per_second,
        avg_ms=avg_ms,
        latency_p50_ms=_percentile(durations_ms, 50.0),
        latency_p95_ms=_percentile(durations_ms, 95.0),
        latency_p99_ms=_percentile(durations_ms, 99.0),
        latency_max_ms=round(max(durations_ms), 4) if durations_ms else 0.0,
    )


def run_benchmark(
    csv_path: Path,
    target_events: int = 100_000,
    batch_size: int = 256,
    warmup_events: int = 1_000,
    window_limit: int = 25,
) -> FlinkRuntimeSliceBenchmarkResult:
    rows = _load_rows(csv_path)
    total_iterations = target_events + warmup_events
    events = 0
    invalid_events = 0
    raw_bytes = 0
    normalized_bytes = 0
    processed_bytes = 0
    batch_count = 0
    latencies_ms: list[float] = []
    keyed_state: dict[str, RollingWindowState] = {}
    mapping_validation_ms: list[float] = []
    record_build_ms: list[float] = []
    keyed_state_ms: list[float] = []
    serialization_ms: list[float] = []

    start = time.perf_counter()
    rows_iter = cycle(rows)

    for index in range(total_iterations):
        row = next(rows_iter)
        started = time.perf_counter()

        stage_started = started
        mapped = map_row_to_event(row, DEFAULT_MAPPING)
        event, dlq = validate_event(mapped)
        mapping_validation_elapsed_ms = (time.perf_counter() - stage_started) * 1000.0
        if event is None or dlq is not None:
            invalid_events += 1
            continue

        stage_started = time.perf_counter()
        raw_payload = to_json_bytes(mapped)
        runtime_event = RuntimeEventRecord.from_industrial_event(event)
        record_build_elapsed_ms = (time.perf_counter() - stage_started) * 1000.0

        stage_started = time.perf_counter()
        key = runtime_event.asset_id
        window = keyed_state.get(key)
        if window is None:
            window = RollingWindowState(maxlen=window_limit)
            keyed_state[key] = window

        temperature_avg, vibration_avg, window_size = window.append(runtime_event)
        processed = build_runtime_event_payload(
            runtime_event,
            temperature_avg_c=temperature_avg,
            vibration_avg_mm_s=vibration_avg,
            window_size=window_size,
        )
        keyed_state_elapsed_ms = (time.perf_counter() - stage_started) * 1000.0

        stage_started = time.perf_counter()
        normalized_payload = to_json_bytes(runtime_event)
        processed_payload = to_json_bytes(processed)
        serialization_elapsed_ms = (time.perf_counter() - stage_started) * 1000.0

        if index >= warmup_events:
            events += 1
            latencies_ms.append((time.perf_counter() - started) * 1000.0)
            mapping_validation_ms.append(mapping_validation_elapsed_ms)
            record_build_ms.append(record_build_elapsed_ms)
            keyed_state_ms.append(keyed_state_elapsed_ms)
            serialization_ms.append(serialization_elapsed_ms)
            raw_bytes += len(raw_payload)
            normalized_bytes += len(normalized_payload)
            processed_bytes += len(processed_payload)
            if events % batch_size == 0:
                batch_count += 1

    if events and events % batch_size:
        batch_count += 1

    elapsed = max(time.perf_counter() - start, 1e-9)
    return FlinkRuntimeSliceBenchmarkResult(
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
        stage_breakdown=(
            _stage_result("mapping_validation", mapping_validation_ms),
            _stage_result("record_build", record_build_ms),
            _stage_result("keyed_state_enrichment", keyed_state_ms),
            _stage_result("serialization", serialization_ms),
        ),
    )


def format_result(result: FlinkRuntimeSliceBenchmarkResult) -> str:
    lines = [
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
    if result.stage_breakdown:
        lines.extend(
            [
                "",
                "stage | ops | avg_ms | p50_ms | p95_ms | p99_ms | max_ms | ops/sec",
                "-" * 110,
            ]
        )
        for stage in result.stage_breakdown:
            lines.append(
                f"{stage.name} | {stage.operations} | {stage.avg_ms} | {stage.latency_p50_ms} | "
                f"{stage.latency_p95_ms} | {stage.latency_p99_ms} | {stage.latency_max_ms} | {stage.events_per_second}"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the keyed-state Flink runtime contract used for the distributed processor.")
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

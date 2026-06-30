from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Any

from services.common.normalize import normalize_runtime_event
from services.datasets.replayer import map_row_to_event, read_csv_rows
from services.edge_ingest.model import to_json_bytes, validate_event
from services.processor.scoring import score_event, severity_for


@dataclass(frozen=True)
class BenchmarkResult:
    csv_path: str
    events: int
    invalid_events: int
    batches: int
    batch_size: int
    elapsed_seconds: float
    events_per_second: float
    serialized_bytes: int
    live_db_events_per_second: float | None = None


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


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    rows = list(read_csv_rows(csv_path))
    if not rows:
        raise ValueError(f"benchmark input is empty: {csv_path}")
    return rows


def _process_row(row: dict[str, str]) -> tuple[dict[str, Any] | None, bytes | None]:
    mapped = map_row_to_event(row, DEFAULT_MAPPING)
    event, dlq = validate_event(mapped)
    if dlq is not None:
        return None, None

    normalized = normalize_runtime_event(event.model_dump(mode="json"))
    temperature = float(normalized.get("temperature_c", 0))
    vibration = float(normalized.get("vibration_mm_s", 0))
    anomaly_score = score_event(normalized, temperature_avg=temperature, vibration_avg=vibration, detector=None)
    normalized["anomaly_score"] = anomaly_score
    normalized["severity"] = severity_for(anomaly_score)
    return normalized, to_json_bytes(normalized)


def run_benchmark(
    csv_path: Path,
    target_events: int = 100_000,
    batch_size: int = 256,
    warmup_events: int = 1_000,
    include_live_db: bool = False,
) -> BenchmarkResult:
    rows = _load_rows(csv_path)
    total_iterations = target_events + warmup_events
    events = 0
    invalid_events = 0
    batches = 0
    serialized_bytes = 0
    batch: list[dict[str, Any]] = []

    start = time.perf_counter()
    rows_iter = cycle(rows)

    live_db_start = None
    live_db_events = 0

    def flush_batch(current_batch: list[dict[str, Any]]) -> None:
        nonlocal batches, serialized_bytes, live_db_start, live_db_events
        if not current_batch:
            return
        batches += 1
        if include_live_db:
            from services.historian.client import insert_processed_events

            if live_db_start is None:
                live_db_start = time.perf_counter()
            insert_processed_events(current_batch)
            live_db_events += len(current_batch)

    for index in range(total_iterations):
        row = next(rows_iter)
        normalized, payload = _process_row(row)
        if normalized is None or payload is None:
            invalid_events += 1
            continue

        if index >= warmup_events:
            events += 1
            batch.append(normalized)
            serialized_bytes += len(payload)
            if len(batch) >= batch_size:
                flush_batch(batch)
                batch = []

    flush_batch(batch)
    elapsed = max(time.perf_counter() - start, 1e-9)
    live_db_eps = None
    if include_live_db and live_db_start is not None and live_db_events > 0:
        live_db_eps = round(live_db_events / max(time.perf_counter() - live_db_start, 1e-9), 2)

    return BenchmarkResult(
        csv_path=str(csv_path),
        events=events,
        invalid_events=invalid_events,
        batches=batches,
        batch_size=batch_size,
        elapsed_seconds=round(elapsed, 4),
        events_per_second=round(events / elapsed, 2),
        serialized_bytes=serialized_bytes,
        live_db_events_per_second=live_db_eps,
    )


def format_result(result: BenchmarkResult) -> str:
    lines = [
        f"csv={result.csv_path}",
        f"events={result.events}",
        f"invalid_events={result.invalid_events}",
        f"batches={result.batches}",
        f"batch_size={result.batch_size}",
        f"elapsed_seconds={result.elapsed_seconds}",
        f"events_per_second={result.events_per_second}",
        f"serialized_bytes={result.serialized_bytes}",
    ]
    if result.live_db_events_per_second is not None:
        lines.append(f"live_db_events_per_second={result.live_db_events_per_second}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the mixed industrial replay pack")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/benchmarks/industrial_mixed_benchmark.csv"),
        help="Replay pack to benchmark",
    )
    parser.add_argument("--events", type=int, default=100_000, help="Target events to measure")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size used for the benchmark")
    parser.add_argument("--warmup-events", type=int, default=1_000, help="Warmup events excluded from the measurement")
    parser.add_argument("--live-db", action="store_true", help="Also execute historian batch writes if the DB is reachable")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(
        csv_path=args.csv,
        target_events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        include_live_db=args.live_db,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

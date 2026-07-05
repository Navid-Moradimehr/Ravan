from __future__ import annotations

import argparse
from dataclasses import dataclass
from statistics import mean, median, pstdev
from pathlib import Path

from services.benchmarks.end_to_end_pipeline import run_benchmark as run_end_to_end_pipeline_benchmark
from services.benchmarks.flink_runtime_slice import run_benchmark as run_flink_runtime_slice_benchmark


VALID_RUNTIME_MODES = {"python-fallback", "flink-local", "flink-production"}


@dataclass(frozen=True)
class ProductionPipelineBenchmarkResult:
    csv_path: str
    runtime_mode: str
    execution_path: str
    events: int
    invalid_events: int
    batches: int
    batch_size: int
    window_limit: int
    elapsed_seconds: float
    events_per_second: float
    serialized_bytes: int
    roundtrip_bytes: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float
    stage_breakdown: tuple[object, ...] = ()


@dataclass(frozen=True)
class ProductionPipelineRepeatabilityResult:
    csv_path: str
    runtime_mode: str
    wire_format: str
    repeat_count: int
    runs: tuple[ProductionPipelineBenchmarkResult, ...]
    average_events_per_second: float
    median_events_per_second: float
    stdev_events_per_second: float
    min_events_per_second: float
    max_events_per_second: float
    average_latency_p99_ms: float
    median_latency_p99_ms: float
    stdev_latency_p99_ms: float
    min_latency_p99_ms: float
    max_latency_p99_ms: float
    baseline_label: str = ""
    baseline_events_per_second: float | None = None
    baseline_latency_p99_ms: float | None = None
    delta_events_per_second: float | None = None
    delta_events_percent: float | None = None
    delta_latency_p99_ms: float | None = None
    delta_latency_percent: float | None = None


def run_benchmark(
    csv_path: Path,
    target_events: int = 100_000,
    batch_size: int = 256,
    warmup_events: int = 1_000,
    window_limit: int = 25,
    *,
    runtime_mode: str = "python-fallback",
    wire_format: str = "json",
) -> ProductionPipelineBenchmarkResult:
    runtime_mode = runtime_mode.lower()
    if runtime_mode not in VALID_RUNTIME_MODES:
        raise ValueError(f"runtime_mode must be one of {sorted(VALID_RUNTIME_MODES)}")

    if runtime_mode == "python-fallback":
        result = run_end_to_end_pipeline_benchmark(
            csv_path,
            target_events=target_events,
            batch_size=batch_size,
            warmup_events=warmup_events,
            window_limit=window_limit,
            wire_format=wire_format,
        )
        return ProductionPipelineBenchmarkResult(
            csv_path=result.csv_path,
            runtime_mode=runtime_mode,
            execution_path="end_to_end_pipeline",
            events=result.events,
            invalid_events=result.invalid_events,
            batches=result.batches,
            batch_size=result.batch_size,
            window_limit=result.window_limit,
            elapsed_seconds=result.elapsed_seconds,
            events_per_second=result.events_per_second,
            serialized_bytes=result.payload_bytes,
            roundtrip_bytes=result.roundtrip_bytes,
            latency_p50_ms=result.latency_p50_ms,
            latency_p95_ms=result.latency_p95_ms,
            latency_p99_ms=result.latency_p99_ms,
            latency_max_ms=result.latency_max_ms,
            stage_breakdown=result.stage_breakdown,
        )

    result = run_flink_runtime_slice_benchmark(
        csv_path,
        target_events=target_events,
        batch_size=batch_size,
        warmup_events=warmup_events,
        window_limit=window_limit,
    )
    return ProductionPipelineBenchmarkResult(
        csv_path=result.csv_path,
        runtime_mode=runtime_mode,
        execution_path="flink_runtime_slice",
        events=result.events,
        invalid_events=result.invalid_events,
        batches=result.batches,
        batch_size=result.batch_size,
        window_limit=result.window_limit,
        elapsed_seconds=result.elapsed_seconds,
        events_per_second=result.events_per_second,
        serialized_bytes=result.serialized_bytes,
        roundtrip_bytes=result.serialized_bytes,
        latency_p50_ms=result.latency_p50_ms,
        latency_p95_ms=result.latency_p95_ms,
        latency_p99_ms=result.latency_p99_ms,
        latency_max_ms=result.latency_max_ms,
        stage_breakdown=result.stage_breakdown,
    )


def run_repeatability(
    csv_path: Path,
    target_events: int = 100_000,
    batch_size: int = 256,
    warmup_events: int = 1_000,
    window_limit: int = 25,
    *,
    runtime_mode: str = "python-fallback",
    wire_format: str = "json",
    repeat_count: int = 3,
    baseline_label: str = "",
    baseline_events_per_second: float | None = None,
    baseline_latency_p99_ms: float | None = None,
) -> ProductionPipelineRepeatabilityResult:
    runs = [
        run_benchmark(
            csv_path,
            target_events=target_events,
            batch_size=batch_size,
            warmup_events=warmup_events,
            window_limit=window_limit,
            runtime_mode=runtime_mode,
            wire_format=wire_format,
        )
        for _ in range(max(1, repeat_count))
    ]
    events = [run.events_per_second for run in runs]
    latencies = [run.latency_p99_ms for run in runs]
    average_events = round(mean(events), 2)
    median_events = round(median(events), 2)
    stdev_events = round(pstdev(events), 2) if len(events) > 1 else 0.0
    min_events = round(min(events), 2)
    max_events = round(max(events), 2)
    average_latency = round(mean(latencies), 4)
    median_latency = round(median(latencies), 4)
    stdev_latency = round(pstdev(latencies), 4) if len(latencies) > 1 else 0.0
    min_latency = round(min(latencies), 4)
    max_latency = round(max(latencies), 4)

    delta_events = None
    delta_events_percent = None
    delta_latency = None
    delta_latency_percent = None
    if baseline_events_per_second is not None:
        delta_events = round(median_events - baseline_events_per_second, 2)
        delta_events_percent = round(((median_events - baseline_events_per_second) / baseline_events_per_second) * 100.0, 2) if baseline_events_per_second else None
    if baseline_latency_p99_ms is not None:
        delta_latency = round(median_latency - baseline_latency_p99_ms, 4)
        delta_latency_percent = round(((median_latency - baseline_latency_p99_ms) / baseline_latency_p99_ms) * 100.0, 2) if baseline_latency_p99_ms else None

    return ProductionPipelineRepeatabilityResult(
        csv_path=str(csv_path),
        runtime_mode=runtime_mode,
        wire_format=wire_format,
        repeat_count=len(runs),
        runs=tuple(runs),
        average_events_per_second=average_events,
        median_events_per_second=median_events,
        stdev_events_per_second=stdev_events,
        min_events_per_second=min_events,
        max_events_per_second=max_events,
        average_latency_p99_ms=average_latency,
        median_latency_p99_ms=median_latency,
        stdev_latency_p99_ms=stdev_latency,
        min_latency_p99_ms=min_latency,
        max_latency_p99_ms=max_latency,
        baseline_label=baseline_label,
        baseline_events_per_second=baseline_events_per_second,
        baseline_latency_p99_ms=baseline_latency_p99_ms,
        delta_events_per_second=delta_events,
        delta_events_percent=delta_events_percent,
        delta_latency_p99_ms=delta_latency,
        delta_latency_percent=delta_latency_percent,
    )


def format_result(result: ProductionPipelineBenchmarkResult) -> str:
    lines = [
        f"csv={result.csv_path}",
        f"runtime_mode={result.runtime_mode}",
        f"execution_path={result.execution_path}",
        f"events={result.events}",
        f"invalid_events={result.invalid_events}",
        f"batches={result.batches}",
        f"batch_size={result.batch_size}",
        f"window_limit={result.window_limit}",
        f"elapsed_seconds={result.elapsed_seconds}",
        f"events_per_second={result.events_per_second}",
        f"serialized_bytes={result.serialized_bytes}",
        f"roundtrip_bytes={result.roundtrip_bytes}",
        f"latency_p50_ms={result.latency_p50_ms}",
        f"latency_p95_ms={result.latency_p95_ms}",
        f"latency_p99_ms={result.latency_p99_ms}",
        f"latency_max_ms={result.latency_max_ms}",
    ]
    if result.stage_breakdown:
        lines.extend(["", "stage | ops | avg_ms | p50_ms | p95_ms | p99_ms | max_ms | ops/sec", "-" * 110])
        for stage in result.stage_breakdown:
            lines.append(
                f"{stage.name} | {stage.operations} | {stage.avg_ms} | {stage.latency_p50_ms} | "
                f"{stage.latency_p95_ms} | {stage.latency_p99_ms} | {stage.latency_max_ms} | {stage.events_per_second}"
            )
    return "\n".join(lines)


def format_repeatability_result(result: ProductionPipelineRepeatabilityResult) -> str:
    lines = [
        f"csv={result.csv_path}",
        f"runtime_mode={result.runtime_mode}",
        f"wire_format={result.wire_format}",
        f"repeat_count={result.repeat_count}",
        f"avg_events_per_second={result.average_events_per_second}",
        f"median_events_per_second={result.median_events_per_second}",
        f"stdev_events_per_second={result.stdev_events_per_second}",
        f"min_events_per_second={result.min_events_per_second}",
        f"max_events_per_second={result.max_events_per_second}",
        f"avg_latency_p99_ms={result.average_latency_p99_ms}",
        f"median_latency_p99_ms={result.median_latency_p99_ms}",
        f"stdev_latency_p99_ms={result.stdev_latency_p99_ms}",
        f"min_latency_p99_ms={result.min_latency_p99_ms}",
        f"max_latency_p99_ms={result.max_latency_p99_ms}",
    ]
    if result.baseline_label:
        lines.extend(
            [
                f"baseline_label={result.baseline_label}",
                f"baseline_events_per_second={result.baseline_events_per_second}",
                f"baseline_latency_p99_ms={result.baseline_latency_p99_ms}",
                f"delta_events_per_second={result.delta_events_per_second}",
                f"delta_events_percent={result.delta_events_percent}",
                f"delta_latency_p99_ms={result.delta_latency_p99_ms}",
                f"delta_latency_percent={result.delta_latency_percent}",
            ]
        )
    if result.runs:
        lines.extend(["", "run | events/sec | p99_ms | invalid_events | execution_path", "-" * 72])
        for idx, run in enumerate(result.runs, start=1):
            lines.append(
                f"{idx} | {run.events_per_second} | {run.latency_p99_ms} | {run.invalid_events} | {run.execution_path}"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the production pipeline contract for the selected runtime mode.")
    parser.add_argument("--csv", type=Path, default=Path("data/benchmarks/industrial_mixed_benchmark.csv"))
    parser.add_argument("--events", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--warmup-events", type=int, default=1_000)
    parser.add_argument("--window-limit", type=int, default=25)
    parser.add_argument("--runtime-mode", choices=sorted(VALID_RUNTIME_MODES), default="python-fallback")
    parser.add_argument("--wire-format", choices=("json", "msgpack"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(
        csv_path=args.csv,
        target_events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        window_limit=args.window_limit,
        runtime_mode=args.runtime_mode,
        wire_format=args.wire_format,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

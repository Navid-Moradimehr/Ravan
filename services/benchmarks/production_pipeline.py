from __future__ import annotations

import argparse
from dataclasses import dataclass
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

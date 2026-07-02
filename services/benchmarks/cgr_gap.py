from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from services.benchmarks.cgr_stream_slice import StreamingSliceBenchmarkResult
from services.benchmarks.cgr_stream_slice import run_benchmark as run_cgr_stream_slice_benchmark
from services.benchmarks.flink_runtime_slice import FlinkRuntimeSliceBenchmarkResult
from services.benchmarks.flink_runtime_slice import run_benchmark as run_flink_runtime_slice_benchmark
from services.benchmarks.mixed_replay import BenchmarkResult as MixedReplayResult
from services.benchmarks.mixed_replay import run_benchmark as run_mixed_replay_benchmark
from services.benchmarks.real_world_simulator import RealWorldSimulatorResult
from services.benchmarks.real_world_simulator import run_suite as run_real_world_simulator_suite
from services.benchmarks.site_profile_matrix import SiteProfileMatrixResult
from services.benchmarks.site_profile_matrix import run_matrix as run_site_profile_matrix


CGR_TARGET_EVENTS_PER_SECOND = 2_000_000.0
CGR_TARGET_P99_MS = 80.0
DOCUMENTED_FULL_PIPELINE_EVENTS_PER_SECOND = 125_830.0


@dataclass(frozen=True)
class GapMetric:
    label: str
    observed_events_per_second: float
    target_events_per_second: float
    gap_multiplier: float
    gap_events_per_second: float
    gap_percent: float
    note: str


@dataclass(frozen=True)
class LatencyMetric:
    label: str
    observed_p99_ms: float
    target_p99_ms: float
    gap_ms: float
    gap_percent: float
    note: str


@dataclass(frozen=True)
class CgrGapReport:
    cgr_target_events_per_second: float
    cgr_target_p99_ms: float
    documented_full_pipeline_events_per_second: float
    documented_full_pipeline_note: str
    mixed_replay: MixedReplayResult
    cgr_stream_slice: StreamingSliceBenchmarkResult
    flink_runtime_slice: FlinkRuntimeSliceBenchmarkResult
    real_world_simulator: RealWorldSimulatorResult
    site_profile_matrix: SiteProfileMatrixResult
    metrics: tuple[GapMetric, ...]
    latency_metrics: tuple[LatencyMetric, ...]
    latency_note: str

    @property
    def best_observed_events_per_second(self) -> float:
        if not self.metrics:
            return 0.0
        return max(metric.observed_events_per_second for metric in self.metrics)


def _gap_metric(label: str, observed_events_per_second: float, note: str) -> GapMetric:
    target = CGR_TARGET_EVENTS_PER_SECOND
    if observed_events_per_second <= 0:
        return GapMetric(
            label=label,
            observed_events_per_second=0.0,
            target_events_per_second=target,
            gap_multiplier=0.0,
            gap_events_per_second=target,
            gap_percent=100.0,
            note=note,
        )

    multiplier = round(target / observed_events_per_second, 2)
    gap_events_per_second = round(target - observed_events_per_second, 2)
    gap_percent = round((1.0 - (observed_events_per_second / target)) * 100.0, 2)
    return GapMetric(
        label=label,
        observed_events_per_second=round(observed_events_per_second, 2),
        target_events_per_second=target,
        gap_multiplier=multiplier,
        gap_events_per_second=gap_events_per_second,
        gap_percent=gap_percent,
        note=note,
    )


def run_report(
    manifest_path: Path,
    baseline_csv: Path,
    *,
    site_ids: Iterable[str] | None = None,
    events: int = 10_000,
    batch_size: int = 256,
    warmup_events: int = 0,
    min_average_events_per_second: float = 1000.0,
    cgr_target_events_per_second: float = CGR_TARGET_EVENTS_PER_SECOND,
    cgr_target_p99_ms: float = CGR_TARGET_P99_MS,
    documented_full_pipeline_events_per_second: float = DOCUMENTED_FULL_PIPELINE_EVENTS_PER_SECOND,
) -> CgrGapReport:
    mixed_replay = run_mixed_replay_benchmark(
        baseline_csv,
        target_events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
    )
    cgr_stream_slice = run_cgr_stream_slice_benchmark(
        baseline_csv,
        target_events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
    )
    flink_runtime_slice = run_flink_runtime_slice_benchmark(
        baseline_csv,
        target_events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
    )
    real_world_simulator = run_real_world_simulator_suite(
        baseline_csv=baseline_csv,
        events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
    )
    site_profile_matrix = run_site_profile_matrix(
        manifest_path,
        baseline_csv,
        site_ids=site_ids,
        events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
        min_average_events_per_second=min_average_events_per_second,
    )

    metrics = [
        _gap_metric(
            "documented_full_pipeline",
            documented_full_pipeline_events_per_second,
            "reference benchmark recorded in docs/benchmark-results.md; remeasure on target hardware before sizing",
        ),
        _gap_metric(
            "mixed_replay",
            mixed_replay.events_per_second,
            "current replay path over the mixed industrial pack",
        ),
        _gap_metric(
            "cgr_stream_slice",
            cgr_stream_slice.events_per_second,
            "isolated stream-processing slice: validate -> normalize -> window -> score -> serialize",
        ),
        _gap_metric(
            "flink_runtime_slice",
            flink_runtime_slice.events_per_second,
            "keyed-state Flink contract: validate -> normalize -> key -> state -> score -> serialize",
        ),
        _gap_metric(
            "real_world_average",
            real_world_simulator.average_events_per_second,
            "average across the simulated real-world benchmark cases",
        ),
    ]
    latency_metrics = [
        LatencyMetric(
            label="mixed_replay",
            observed_p99_ms=mixed_replay.latency_p99_ms,
            target_p99_ms=cgr_target_p99_ms,
            gap_ms=round(cgr_target_p99_ms - mixed_replay.latency_p99_ms, 4),
            gap_percent=round((1.0 - (mixed_replay.latency_p99_ms / cgr_target_p99_ms)) * 100.0, 2)
            if cgr_target_p99_ms > 0
            else 0.0,
            note="current replay path over the mixed industrial pack",
        ),
        LatencyMetric(
            label="cgr_stream_slice",
            observed_p99_ms=cgr_stream_slice.latency_p99_ms,
            target_p99_ms=cgr_target_p99_ms,
            gap_ms=round(cgr_target_p99_ms - cgr_stream_slice.latency_p99_ms, 4),
            gap_percent=round((1.0 - (cgr_stream_slice.latency_p99_ms / cgr_target_p99_ms)) * 100.0, 2)
            if cgr_target_p99_ms > 0
            else 0.0,
            note="isolated stream-processing slice",
        ),
        LatencyMetric(
            label="flink_runtime_slice",
            observed_p99_ms=flink_runtime_slice.latency_p99_ms,
            target_p99_ms=cgr_target_p99_ms,
            gap_ms=round(cgr_target_p99_ms - flink_runtime_slice.latency_p99_ms, 4),
            gap_percent=round((1.0 - (flink_runtime_slice.latency_p99_ms / cgr_target_p99_ms)) * 100.0, 2)
            if cgr_target_p99_ms > 0
            else 0.0,
            note="keyed-state Flink contract",
        ),
        LatencyMetric(
            label="real_world_average",
            observed_p99_ms=real_world_simulator.average_latency_p99_ms,
            target_p99_ms=cgr_target_p99_ms,
            gap_ms=round(cgr_target_p99_ms - real_world_simulator.average_latency_p99_ms, 4),
            gap_percent=round((1.0 - (real_world_simulator.average_latency_p99_ms / cgr_target_p99_ms)) * 100.0, 2)
            if cgr_target_p99_ms > 0
            else 0.0,
            note="average across the simulated real-world benchmark cases",
        ),
    ]
    if site_profile_matrix.runs:
        metrics.append(
            _gap_metric(
                "site_profile_average",
                round(sum(run.average_events_per_second for run in site_profile_matrix.runs) / len(site_profile_matrix.runs), 2),
                "average across selected site profiles",
            )
        )
        best_run = max(site_profile_matrix.runs, key=lambda run: run.average_events_per_second)
        metrics.append(
            _gap_metric(
                f"site_profile_best:{best_run.site_id}",
                best_run.average_events_per_second,
                f"best selected site profile ({best_run.deployment_mode})",
            )
        )
        average_latency = round(sum(run.latency_p99_ms for run in site_profile_matrix.runs) / len(site_profile_matrix.runs), 4)
        best_latency_run = min(site_profile_matrix.runs, key=lambda run: run.latency_p99_ms)
        latency_metrics.append(
            LatencyMetric(
                label="site_profile_average",
                observed_p99_ms=average_latency,
                target_p99_ms=cgr_target_p99_ms,
                gap_ms=round(cgr_target_p99_ms - average_latency, 4),
                gap_percent=round((1.0 - (average_latency / cgr_target_p99_ms)) * 100.0, 2)
                if cgr_target_p99_ms > 0
                else 0.0,
                note="average across selected site profiles",
            )
        )
        latency_metrics.append(
            LatencyMetric(
                label=f"site_profile_best:{best_latency_run.site_id}",
                observed_p99_ms=best_latency_run.latency_p99_ms,
                target_p99_ms=cgr_target_p99_ms,
                gap_ms=round(cgr_target_p99_ms - best_latency_run.latency_p99_ms, 4),
                gap_percent=round((1.0 - (best_latency_run.latency_p99_ms / cgr_target_p99_ms)) * 100.0, 2)
                if cgr_target_p99_ms > 0
                else 0.0,
                note=f"best latency site profile ({best_latency_run.deployment_mode})",
            )
        )

    latency_note = (
        f"Current suite now measures replay p99 latency; compare it against the CGR target of "
        f"{cgr_target_p99_ms} ms."
    )

    return CgrGapReport(
        cgr_target_events_per_second=cgr_target_events_per_second,
        cgr_target_p99_ms=cgr_target_p99_ms,
        documented_full_pipeline_events_per_second=documented_full_pipeline_events_per_second,
        documented_full_pipeline_note="latest documented full-pipeline benchmark reference from the repo",
        mixed_replay=mixed_replay,
        cgr_stream_slice=cgr_stream_slice,
        flink_runtime_slice=flink_runtime_slice,
        real_world_simulator=real_world_simulator,
        site_profile_matrix=site_profile_matrix,
        metrics=tuple(metrics),
        latency_metrics=tuple(latency_metrics),
        latency_note=latency_note,
    )


def format_result(result: CgrGapReport) -> str:
    lines = [
        "cgr gap report",
        "=" * 40,
        f"cgr_target_events_per_second={result.cgr_target_events_per_second}",
        f"cgr_target_p99_ms={result.cgr_target_p99_ms}",
        f"documented_full_pipeline_events_per_second={result.documented_full_pipeline_events_per_second}",
        f"documented_full_pipeline_note={result.documented_full_pipeline_note}",
        f"mixed_replay_events_per_second={result.mixed_replay.events_per_second}",
        f"cgr_stream_slice_events_per_second={result.cgr_stream_slice.events_per_second}",
        f"flink_runtime_slice_events_per_second={result.flink_runtime_slice.events_per_second}",
        f"real_world_average_events_per_second={result.real_world_simulator.average_events_per_second}",
        f"site_profile_matrix_passed={str(result.site_profile_matrix.passed).lower()}",
        f"latency_note={result.latency_note}",
        "",
        "metric | observed_events/sec | gap_x | gap_events/sec | gap_percent | note",
        "-" * 100,
    ]
    for metric in result.metrics:
        lines.append(
            f"{metric.label} | {metric.observed_events_per_second} | {metric.gap_multiplier} | "
            f"{metric.gap_events_per_second} | {metric.gap_percent} | {metric.note}"
        )
    lines.extend([
        "",
        "latency metric | observed_p99_ms | target_p99_ms | gap_ms | gap_percent | note",
        "-" * 100,
    ])
    for metric in result.latency_metrics:
        lines.append(
            f"{metric.label} | {metric.observed_p99_ms} | {metric.target_p99_ms} | "
            f"{metric.gap_ms} | {metric.gap_percent} | {metric.note}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare local industrial benchmark results against the public CGR streaming claims.")
    parser.add_argument("--manifest", type=Path, default=Path("config/project-manifest.yaml"))
    parser.add_argument("--csv", type=Path, default=Path("data/benchmarks/industrial_mixed_benchmark.csv"))
    parser.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--warmup-events", type=int, default=0)
    parser.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    parser.add_argument("--cgr-events-per-second", type=float, default=CGR_TARGET_EVENTS_PER_SECOND)
    parser.add_argument("--cgr-p99-ms", type=float, default=CGR_TARGET_P99_MS)
    parser.add_argument(
        "--documented-full-pipeline-events-per-second",
        type=float,
        default=DOCUMENTED_FULL_PIPELINE_EVENTS_PER_SECOND,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
    report = run_report(
        args.manifest,
        args.csv,
        site_ids=site_ids,
        events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        min_average_events_per_second=args.min_average_events_per_second,
        cgr_target_events_per_second=args.cgr_events_per_second,
        cgr_target_p99_ms=args.cgr_p99_ms,
        documented_full_pipeline_events_per_second=args.documented_full_pipeline_events_per_second,
    )
    print(format_result(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

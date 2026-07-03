from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Iterable

from services.benchmarks.real_world_simulator import RealWorldSimulatorResult, format_result as format_simulator_result, run_suite as run_real_world_simulator_suite
from services.common.project_manifest import load_project_manifest
from services.common.site_profiles import load_site_profile


@dataclass(frozen=True)
class SiteProfileBenchmarkResult:
    site_id: str
    deployment_mode: str
    profile_path: str
    average_events_per_second: float
    median_events_per_second: float
    stdev_events_per_second: float
    min_events_per_second: float
    max_events_per_second: float
    repeat_count: int
    latency_p99_ms: float
    passed: bool
    detail: str
    simulator: RealWorldSimulatorResult


@dataclass(frozen=True)
class SiteProfileMatrixResult:
    runs: tuple[SiteProfileBenchmarkResult, ...]

    @property
    def passed(self) -> bool:
        return all(run.passed for run in self.runs)


def _threshold_for_mode(deployment_mode: str, default: float) -> float:
    if deployment_mode == "single-site":
        return max(default, 500.0)
    if deployment_mode == "plant-local":
        return max(default, 750.0)
    if deployment_mode == "federated":
        return max(default, 600.0)
    return default


def run_matrix(
    manifest_path: Path,
    baseline_csv: Path,
    *,
    site_ids: Iterable[str] | None = None,
    events: int = 10_000,
    batch_size: int = 256,
    warmup_events: int = 0,
    min_average_events_per_second: float = 1000.0,
    repeat_count: int = 1,
) -> SiteProfileMatrixResult:
    manifest = load_project_manifest(manifest_path)
    selected_ids = list(site_ids) if site_ids is not None else [site.site_id for site in manifest.sites]
    runs: list[SiteProfileBenchmarkResult] = []

    for site in manifest.sites:
        if site.site_id not in selected_ids:
            continue
        profile = load_site_profile(site.profile_path)
        simulator_runs = [
            run_real_world_simulator_suite(
                baseline_csv=baseline_csv,
                events=events,
                batch_size=batch_size,
                warmup_events=warmup_events,
            )
            for _ in range(max(1, repeat_count))
        ]
        observed = [simulator.average_events_per_second for simulator in simulator_runs]
        aggregate = simulator_runs[-1]
        average = round(mean(observed), 2)
        med = round(median(observed), 2)
        spread = round(pstdev(observed), 2) if len(observed) > 1 else 0.0
        min_observed = round(min(observed), 2)
        max_observed = round(max(observed), 2)
        threshold = _threshold_for_mode(profile.deployment_mode, min_average_events_per_second)
        passed = med >= threshold and all(
            case.invalid_events == 0
            for simulator in simulator_runs
            for case in simulator.cases
        )
        detail = (
            f"threshold={threshold} median={med} avg={average} stdev={spread} "
            f"min={min_observed} max={max_observed} p99={aggregate.average_latency_p99_ms} "
            f"repeat_count={len(simulator_runs)} invalid_events_ok={all(case.invalid_events == 0 for simulator in simulator_runs for case in simulator.cases)}"
        )
        runs.append(
            SiteProfileBenchmarkResult(
                site_id=site.site_id,
                deployment_mode=profile.deployment_mode,
                profile_path=site.profile_path,
                average_events_per_second=average,
                median_events_per_second=med,
                stdev_events_per_second=spread,
                min_events_per_second=min_observed,
                max_events_per_second=max_observed,
                repeat_count=len(simulator_runs),
                latency_p99_ms=aggregate.average_latency_p99_ms,
                passed=passed,
                detail=detail,
                simulator=aggregate,
            )
        )
    return SiteProfileMatrixResult(runs=tuple(runs))


def format_result(result: SiteProfileMatrixResult) -> str:
    lines = [
        "site_id | deployment_mode | avg_events/sec | median | stdev | p99_ms | passed | detail",
        "-" * 104,
    ]
    for run in result.runs:
        lines.append(
            f"{run.site_id} | {run.deployment_mode} | {run.average_events_per_second} | {run.median_events_per_second} | {run.stdev_events_per_second} | {run.latency_p99_ms} | {str(run.passed).lower()} | {run.detail}"
        )
    if result.runs:
        lines.append("-" * 104)
        lines.append(f"overall | - | - | {str(result.passed).lower()} | -")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run real-world simulator benchmarks per site profile.")
    parser.add_argument("--manifest", type=Path, default=Path("config/project-manifest.yaml"))
    parser.add_argument("--csv", type=Path, default=Path("data/benchmarks/industrial_mixed_benchmark.csv"))
    parser.add_argument("--site-ids", default=None, help="Comma-separated site ids; defaults to all sites in the manifest")
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--warmup-events", type=int, default=0)
    parser.add_argument("--min-average-events-per-second", type=float, default=1000.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    site_ids = [part.strip() for part in args.site_ids.split(",") if part.strip()] if args.site_ids else None
    result = run_matrix(
        args.manifest,
        args.csv,
        site_ids=site_ids,
        events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        min_average_events_per_second=args.min_average_events_per_second,
    )
    print(format_result(result))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

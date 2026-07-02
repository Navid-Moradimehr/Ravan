from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
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
) -> SiteProfileMatrixResult:
    manifest = load_project_manifest(manifest_path)
    selected_ids = list(site_ids) if site_ids is not None else [site.site_id for site in manifest.sites]
    runs: list[SiteProfileBenchmarkResult] = []

    for site in manifest.sites:
        if site.site_id not in selected_ids:
            continue
        profile = load_site_profile(site.profile_path)
        simulator = run_real_world_simulator_suite(
            baseline_csv=baseline_csv,
            events=events,
            batch_size=batch_size,
            warmup_events=warmup_events,
        )
        threshold = _threshold_for_mode(profile.deployment_mode, min_average_events_per_second)
        average = simulator.average_events_per_second
        passed = average >= threshold and all(case.invalid_events == 0 for case in simulator.cases)
        detail = f"threshold={threshold} avg={average} invalid_events_ok={all(case.invalid_events == 0 for case in simulator.cases)}"
        runs.append(
            SiteProfileBenchmarkResult(
                site_id=site.site_id,
                deployment_mode=profile.deployment_mode,
                profile_path=site.profile_path,
                average_events_per_second=average,
                passed=passed,
                detail=detail,
                simulator=simulator,
            )
        )
    return SiteProfileMatrixResult(runs=tuple(runs))


def format_result(result: SiteProfileMatrixResult) -> str:
    lines = [
        "site_id | deployment_mode | avg_events/sec | passed | detail",
        "-" * 90,
    ]
    for run in result.runs:
        lines.append(
            f"{run.site_id} | {run.deployment_mode} | {run.average_events_per_second} | {str(run.passed).lower()} | {run.detail}"
        )
    if result.runs:
        lines.append("-" * 90)
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

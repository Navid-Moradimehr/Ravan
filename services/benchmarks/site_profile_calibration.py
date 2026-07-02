from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from services.benchmarks.site_profile_matrix import SiteProfileMatrixResult, run_matrix as run_site_profile_matrix
from services.common.project_manifest import load_project_manifest
from services.common.site_profiles import load_site_profile


@dataclass(frozen=True)
class SiteProfileCalibrationResult:
    site_id: str
    deployment_mode: str
    profile_path: str
    observed_average_events_per_second: float
    acceptance_threshold: float
    headroom_events_per_second: float
    headroom_ratio: float
    recommended_min_average_events_per_second: float
    recommended_batch_size: int
    passed: bool


@dataclass(frozen=True)
class SiteProfileCalibrationMatrixResult:
    runs: tuple[SiteProfileCalibrationResult, ...]
    benchmark: SiteProfileMatrixResult

    @property
    def passed(self) -> bool:
        return self.benchmark.passed and all(run.passed for run in self.runs)


def _threshold_for_mode(deployment_mode: str, default: float) -> float:
    if deployment_mode == "single-site":
        return max(default, 500.0)
    if deployment_mode == "plant-local":
        return max(default, 750.0)
    if deployment_mode == "federated":
        return max(default, 600.0)
    return max(default, 1000.0)


def _recommended_batch_size(batch_size: int, headroom_ratio: float) -> int:
    if headroom_ratio >= 10.0:
        return max(batch_size, 256)
    if headroom_ratio >= 4.0:
        return max(batch_size, 192)
    if headroom_ratio >= 2.0:
        return max(batch_size, 128)
    return max(64, batch_size // 2)


def run_calibration(
    manifest_path: Path,
    baseline_csv: Path,
    *,
    site_ids: Iterable[str] | None = None,
    events: int = 10_000,
    batch_size: int = 256,
    warmup_events: int = 0,
    min_average_events_per_second: float = 1000.0,
) -> SiteProfileCalibrationMatrixResult:
    manifest = load_project_manifest(manifest_path)
    selected_ids = list(site_ids) if site_ids is not None else [site.site_id for site in manifest.sites]
    benchmark = run_site_profile_matrix(
        manifest_path,
        baseline_csv,
        site_ids=selected_ids,
        events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
        min_average_events_per_second=min_average_events_per_second,
    )
    benchmark_by_site = {run.site_id: run for run in benchmark.runs}
    runs: list[SiteProfileCalibrationResult] = []

    for site in manifest.sites:
        if site.site_id not in selected_ids:
            continue
        profile = load_site_profile(site.profile_path)
        run = benchmark_by_site[site.site_id]
        threshold = _threshold_for_mode(profile.deployment_mode, min_average_events_per_second)
        headroom = run.average_events_per_second - threshold
        ratio = run.average_events_per_second / threshold if threshold > 0 else 0.0
        runs.append(
            SiteProfileCalibrationResult(
                site_id=site.site_id,
                deployment_mode=profile.deployment_mode,
                profile_path=site.profile_path,
                observed_average_events_per_second=run.average_events_per_second,
                acceptance_threshold=threshold,
                headroom_events_per_second=headroom,
                headroom_ratio=round(ratio, 2),
                recommended_min_average_events_per_second=round(max(threshold, run.average_events_per_second * 0.8), 2),
                recommended_batch_size=_recommended_batch_size(batch_size, ratio),
                passed=run.passed and headroom >= 0,
            )
        )
    return SiteProfileCalibrationMatrixResult(runs=tuple(runs), benchmark=benchmark)


def format_result(result: SiteProfileCalibrationMatrixResult) -> str:
    lines = [
        "site_id | deployment_mode | avg_events/sec | threshold | headroom | headroom_ratio | recommended_min | recommended_batch",
        "-" * 120,
    ]
    for run in result.runs:
        lines.append(
            f"{run.site_id} | {run.deployment_mode} | {run.observed_average_events_per_second} | "
            f"{run.acceptance_threshold} | {run.headroom_events_per_second} | {run.headroom_ratio} | "
            f"{run.recommended_min_average_events_per_second} | {run.recommended_batch_size}"
        )
    if result.runs:
        lines.append("-" * 120)
        lines.append(f"overall | - | - | - | - | - | - | {str(result.passed).lower()}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate per-site benchmark thresholds from a mixed replay pack.")
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
    result = run_calibration(
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

from __future__ import annotations

import argparse
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from services.benchmarks.mixed_replay import run_benchmark as run_mixed_replay_benchmark
from services.common.project_manifest import load_project_manifest


@dataclass(frozen=True)
class DeploymentPackBenchmarkResult:
    manifest_path: str
    csv_path: str
    site_id: str
    export_elapsed_seconds: float
    export_file_count: int
    export_files_per_second: float
    systemd_file_count: int
    kubernetes_file_count: int
    replay_events: int
    replay_events_per_second: float
    replay_batches: int
    replay_serialized_bytes: int


def _count_exported_files(paths: Iterable[Path], prefix: Path) -> int:
    seen: set[Path] = set()
    for path in paths:
        seen.add(path.relative_to(prefix))
    return len(seen)


def run_benchmark(
    manifest_path: Path,
    csv_path: Path,
    *,
    site_id: str,
    target_events: int = 10_000,
    batch_size: int = 256,
    warmup_events: int = 0,
) -> DeploymentPackBenchmarkResult:
    manifest = load_project_manifest(manifest_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        started = time.perf_counter()
        systemd_written = manifest.export_bundles(base / "systemd", site_id=site_id, fmt="both", layout="systemd")
        kubernetes_written = manifest.export_bundles(base / "kubernetes", site_id=site_id, fmt="both", layout="kubernetes")
        elapsed = max(time.perf_counter() - started, 1e-9)
        export_file_count = len(systemd_written) + len(kubernetes_written)
        replay = run_mixed_replay_benchmark(
            csv_path,
            target_events=target_events,
            batch_size=batch_size,
            warmup_events=warmup_events,
        )
        return DeploymentPackBenchmarkResult(
            manifest_path=str(manifest_path),
            csv_path=str(csv_path),
            site_id=site_id,
            export_elapsed_seconds=round(elapsed, 4),
            export_file_count=export_file_count,
            export_files_per_second=round(export_file_count / elapsed, 2),
            systemd_file_count=_count_exported_files(systemd_written, base / "systemd"),
            kubernetes_file_count=_count_exported_files(kubernetes_written, base / "kubernetes"),
            replay_events=replay.events,
            replay_events_per_second=replay.events_per_second,
            replay_batches=replay.batches,
            replay_serialized_bytes=replay.serialized_bytes,
        )


def format_result(result: DeploymentPackBenchmarkResult) -> str:
    return "\n".join(
        [
            f"manifest={result.manifest_path}",
            f"csv={result.csv_path}",
            f"site_id={result.site_id}",
            f"export_elapsed_seconds={result.export_elapsed_seconds}",
            f"export_file_count={result.export_file_count}",
            f"export_files_per_second={result.export_files_per_second}",
            f"systemd_file_count={result.systemd_file_count}",
            f"kubernetes_file_count={result.kubernetes_file_count}",
            f"replay_events={result.replay_events}",
            f"replay_events_per_second={result.replay_events_per_second}",
            f"replay_batches={result.replay_batches}",
            f"replay_serialized_bytes={result.replay_serialized_bytes}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark manifest export layouts together with mock replay data.")
    parser.add_argument("--manifest", type=Path, default=Path("config/project-manifest.yaml"))
    parser.add_argument("--csv", type=Path, default=Path("data/benchmarks/industrial_mixed_benchmark.csv"))
    parser.add_argument("--site-id", default="demo-site")
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--warmup-events", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(
        args.manifest,
        args.csv,
        site_id=args.site_id,
        target_events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

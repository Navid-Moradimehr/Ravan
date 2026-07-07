from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from services.common.metadata_artifacts import build_metadata_artifact_bundle


@dataclass(frozen=True)
class MetadataArtifactBenchmarkResult:
    iterations: int
    warmup_iterations: int
    elapsed_seconds: float
    snapshots_per_second: float
    bundle_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_benchmark(
    *,
    iterations: int = 100,
    warmup_iterations: int = 10,
    site_profile_path: Path | str | None = None,
    asset_config: Path | str = Path("config/assets.yaml"),
    project_manifest_path: Path | str = Path("config/project-manifest.yaml"),
    semantic_store_path: Path | str | None = None,
) -> MetadataArtifactBenchmarkResult:
    for _ in range(max(0, warmup_iterations)):
        build_metadata_artifact_bundle(
            site_profile_path=site_profile_path,
            asset_config=asset_config,
            project_manifest_path=project_manifest_path,
            semantic_store_path=semantic_store_path,
        )
    started = perf_counter()
    bundle = None
    for _ in range(max(1, iterations)):
        bundle = build_metadata_artifact_bundle(
            site_profile_path=site_profile_path,
            asset_config=asset_config,
            project_manifest_path=project_manifest_path,
            semantic_store_path=semantic_store_path,
        )
    elapsed = max(perf_counter() - started, 1e-9)
    counts = bundle.metadata_plane["contracts"] if bundle else {}
    return MetadataArtifactBenchmarkResult(
        iterations=max(1, iterations),
        warmup_iterations=max(0, warmup_iterations),
        elapsed_seconds=round(elapsed, 6),
        snapshots_per_second=round(max(1, iterations) / elapsed, 2),
        bundle_counts={
            "metadata_plane_assets": int(bundle.metadata_plane["contracts"]["asset_registry_entries"]) if bundle else 0,
            "metadata_plane_topics": int(bundle.metadata_plane["contracts"]["event_catalog_topics"]) if bundle else 0,
            "schema_count": len(bundle.metadata_plane["registries"]["schemas"]) if bundle else 0,
        },
    )


def format_result(result: MetadataArtifactBenchmarkResult) -> str:
    return "\n".join(
        [
            f"iterations={result.iterations}",
            f"warmup_iterations={result.warmup_iterations}",
            f"elapsed_seconds={result.elapsed_seconds}",
            f"snapshots_per_second={result.snapshots_per_second}",
            f"bundle_counts={result.bundle_counts}",
        ]
    )

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from services.common.training_dataset import compile_bundle


@dataclass(frozen=True)
class TrainingDatasetBenchmark:
    iterations: int
    records_per_iteration: int
    elapsed_seconds: float
    records_per_second: float


def run_benchmark(*, iterations: int = 3, records_per_iteration: int = 1_000) -> TrainingDatasetBenchmark:
    with tempfile.TemporaryDirectory(prefix="datastream-training-benchmark-") as directory:
        root = Path(directory)
        manifest = root / "manifest.yaml"
        manifest.write_text(
            yaml.safe_dump(
                {
                    "dataset_id": "benchmark-v1",
                    "site_id": "benchmark-site",
                    "time_range": "2026-01-01/2026-01-02",
                    "purpose": "jepa",
                    "observation_sources": ["industrial.normalized"],
                    "provenance": {"mapping_version": "benchmark:v1"},
                }
            ),
            encoding="utf-8",
        )
        source = root / "observations.jsonl"
        source.write_text(
            "".join(json.dumps({"event_id": f"e-{index}", "site_id": "benchmark-site", "value": index}) + "\n" for index in range(records_per_iteration)),
            encoding="utf-8",
        )
        started = time.perf_counter()
        for iteration in range(iterations):
            compile_bundle(manifest, root / f"bundle-{iteration}", observations=source)
        elapsed = max(time.perf_counter() - started, 1e-9)
    total = iterations * records_per_iteration
    return TrainingDatasetBenchmark(iterations, records_per_iteration, elapsed, total / elapsed)

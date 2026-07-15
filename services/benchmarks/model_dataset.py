"""Small deterministic benchmark for manifest validation and trajectory builds."""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from services.common.model_dataset import compile_trajectory_bundle


@dataclass(frozen=True)
class ModelDatasetBenchmarkResult:
    records: int
    elapsed_seconds: float
    records_per_second: float
    steps: int

    def to_dict(self) -> dict[str, float | int]:
        return {"records": self.records, "elapsed_seconds": self.elapsed_seconds, "records_per_second": self.records_per_second, "steps": self.steps}


def run_benchmark(records: int = 1000) -> ModelDatasetBenchmarkResult:
    records = max(2, int(records))
    with tempfile.TemporaryDirectory(prefix="datastream-model-benchmark-") as directory:
        root = Path(directory)
        source = root / "observations.jsonl"
        lines = []
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for index in range(records):
            timestamp = (base + timedelta(milliseconds=index * 100)).isoformat().replace("+00:00", "Z")
            lines.append(json.dumps({"event_id": f"e-{index}", "site_id": "plant-a", "asset_id": "pump-1", "tag": "pressure", "value": 4.0 + (index % 10) / 10, "timestamp": timestamp}))
        source.write_text("\n".join(lines), encoding="utf-8")
        manifest = {"manifest_version": 2, "dataset_id": "benchmark", "site_ids": ["plant-a"], "time_range": {}, "purpose": "jepa", "observation_sources": str(source), "alignment": {"sample_interval_ms": 100, "max_skew_ms": 50}, "provenance": {"source": "benchmark"}}
        manifest_path = root / "manifest.yaml"
        manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        started = time.perf_counter()
        result = compile_trajectory_bundle(manifest_path, root / "bundle")
        elapsed = max(time.perf_counter() - started, 1e-9)
        return ModelDatasetBenchmarkResult(records, elapsed, records / elapsed, int(result["quality"]["record_counts"]["steps"]))

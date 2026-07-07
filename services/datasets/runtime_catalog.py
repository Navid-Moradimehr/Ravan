"""Runtime dataset catalog mirrored from docs/testing-data-catalog.md."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetSource:
    dataset_id: str
    name: str
    category: str
    signals: str
    best_use: str
    licensed: bool


DATASET_SOURCES: tuple[DatasetSource, ...] = (
    DatasetSource(
        dataset_id="mock",
        name="Built-in mock generator",
        category="mock",
        signals="Configurable pump/motor/turbine tags with scenario labels",
        best_use="Smoke tests, UI validation, repeatable CI",
        licensed=False,
    ),
    DatasetSource(
        dataset_id="ai4i",
        name="AI4I 2020 Predictive Maintenance",
        category="synthetic",
        signals="Speed, torque, temperatures, tool wear, failure labels",
        best_use="Predictive maintenance demos and severity workflows",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="industrial-benchmark",
        name="Industrial Mixed Benchmark Pack",
        category="benchmark",
        signals="Mixed protocol telemetry across pumps and motors with severity labels",
        best_use="Replay-based load testing and industrial scenario benchmarking",
        licensed=False,
    ),
    DatasetSource(
        dataset_id="cmapss",
        name="NASA C-MAPSS",
        category="synthetic",
        signals="Engine sensors and operating settings, run-to-failure",
        best_use="Degradation and remaining-useful-life experiments",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="ims-bearing",
        name="IMS / NASA Bearing Run-to-Failure",
        category="industrial",
        signals="Vibration time series, run-to-failure",
        best_use="Vibration analytics and anomaly detection",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="skab",
        name="Skoltech Anomaly Benchmark (SKAB)",
        category="industrial",
        signals="Industrial telemetry with anomaly labels",
        best_use="Benchmarking rules vs model-based detectors",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="nab",
        name="Numenta Anomaly Benchmark (NAB)",
        category="industrial",
        signals="Mixed real-world time-series anomalies",
        best_use="Detector benchmarking and baseline scoring",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="swat",
        name="Secure Water Treatment (SWaT)",
        category="security",
        signals="Water treatment process tags, attack and normal traces",
        best_use="ICS security analytics and incident workflows",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="wadi",
        name="Water Distribution (WADI)",
        category="security",
        signals="Process telemetry and attack scenarios",
        best_use="Cybersecurity and multi-stage anomaly correlation",
        licensed=True,
    ),
    DatasetSource(
        dataset_id="mimii",
        name="MIMII machine sound",
        category="multimodal",
        signals="Industrial sound recordings",
        best_use="Future multimodal monitoring (lower priority)",
        licensed=True,
    ),
)


class DatasetCatalog:
    def __init__(
        self,
        sources: list[DatasetSource] | None = None,
        state_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._sources: list[DatasetSource] = list(sources or DATASET_SOURCES)
        self._state_path = Path(state_path) if state_path else None
        if self._state_path and self._state_path.exists():
            self._load_state()
        elif state_path:
            self._persist_state()

    def list_sources(self, category: str | None = None) -> list[DatasetSource]:
        if category:
            return [d for d in self._sources if d.category == category]
        return list(self._sources)

    def get_source(self, dataset_id: str) -> DatasetSource | None:
        for source in self._sources:
            if source.dataset_id == dataset_id:
                return source
        return None

    def register(self, source: DatasetSource) -> None:
        self._sources = [item for item in self._sources if item.dataset_id != source.dataset_id]
        self._sources.append(source)
        self._persist_state()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": [source.__dict__ for source in self._sources],
        }

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive bootstrap path
            raise ValueError(f"failed to load dataset catalog state from {self._state_path}") from exc

        self._sources = [
            DatasetSource(
                dataset_id=item["dataset_id"],
                name=item["name"],
                category=item["category"],
                signals=item["signals"],
                best_use=item["best_use"],
                licensed=bool(item.get("licensed", False)),
            )
            for item in payload.get("sources", [])
        ]

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._state_path)


DATASET_CATALOG_PATH = os.environ.get("DATASET_CATALOG_PATH")
dataset_catalog = DatasetCatalog(state_path=DATASET_CATALOG_PATH)


def list_dataset_sources(category=None):
    return dataset_catalog.list_sources(category=category)


def get_dataset_source(dataset_id):
    return dataset_catalog.get_source(dataset_id)

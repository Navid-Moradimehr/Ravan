"""Runtime dataset catalog mirrored from docs/testing-data-catalog.md."""
from __future__ import annotations

from dataclasses import dataclass


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


def list_dataset_sources(category=None):
    if category:
        return [d for d in DATASET_SOURCES if d.category == category]
    return list(DATASET_SOURCES)


def get_dataset_source(dataset_id):
    for d in DATASET_SOURCES:
        if d.dataset_id == dataset_id:
            return d
    return None

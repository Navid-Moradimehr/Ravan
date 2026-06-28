"""Catalog of real and mock industrial data sources for testing.

Sources:
1. AI4I 2020 (UCI) - Predictive Maintenance Dataset
2. NASA Bearing Dataset (IMS)
3. NASA Turbofan Engine Degradation (C-MAPSS)
4. SKAB (Skoltech Anomaly Benchmark)
5. NAB (Numenta Anomaly Benchmark)
6. SWaT/WADI (Secure Water Treatment)
7. Generated Mock Data (built-in)

All sources can be downloaded, adapted, and replayed into the pipeline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import urllib.request
import zipfile
import shutil


@dataclass
class DataSource:
    name: str
    description: str
    url: str
    local_path: Path
    file_type: str  # "csv", "zip", "tar"
    adapter: Callable[[Path], list[dict[str, Any]]] | None = None
    size_mb: float = 0.0
    license: str = ""
    citation: str = ""


# AI4I 2020 Predictive Maintenance Dataset
AI4I_SOURCE = DataSource(
    name="AI4I 2020 Predictive Maintenance",
    description="""
    10,000 records of machine sensor data with failure labels.
    Columns: UDI, Product ID, Type, Air temperature [K], Process temperature [K],
    Rotational speed [rpm], Torque [Nm], Tool wear [min], Machine failure, TWF, HDF, PWF, OSF, RNF
    """,
    url="https://archive.ics.uci.edu/ml/machine-learning-databases/00601/ai4i2020.csv",
    local_path=Path("data/ai4i2020.csv"),
    file_type="csv",
    size_mb=1.5,
    license="CC BY 4.0",
    citation="S. Matzka, 'Explainable Artificial Intelligence for Predictive Maintenance Applications', 2020",
)

# NASA Bearing Dataset (IMS)
NASA_BEARING_SOURCE = DataSource(
    name="NASA Bearing Dataset (IMS)",
    description="""
    Run-to-failure bearing vibration data from NASA Prognostics Center.
    3 test cases, each with individual bearing vibration signals.
    Sampling rate: 20 kHz, duration until failure.
    """,
    url="https://ti.arc.nasa.gov/c/6/",
    local_path=Path("data/nasa_bearing_ims.zip"),
    file_type="zip",
    size_mb=120.0,
    license="Public Domain (NASA)",
    citation="Qiu et al., 'Bearing Data Set', NASA Ames Prognostics Data Repository, 2007",
)

# NASA C-MAPSS Turbofan Engine
NASA_CMAPSS_SOURCE = DataSource(
    name="NASA C-MAPSS Turbofan Engine",
    description="""
    Simulated turbofan engine degradation data.
    4 operational conditions, 21 sensor measurements per engine.
    Includes run-to-failure trajectories for remaining useful life (RUL) prediction.
    """,
    url="https://ti.arc.nasa.gov/c/13/",
    local_path=Path("data/nasa_cmapss.zip"),
    file_type="zip",
    size_mb=45.0,
    license="Public Domain (NASA)",
    citation="Saxena et al., 'Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation', 2008",
)

# SKAB (Skoltech Anomaly Benchmark)
SKAB_SOURCE = DataSource(
    name="SKAB Anomaly Benchmark",
    description="""
    Multivariate time series with labeled anomalies from a pump testbed.
    8 sensor channels, ground truth anomaly labels, multiple fault types.
    Designed for benchmarking anomaly detection algorithms.
    """,
    url="https://github.com/waico/Skab",
    local_path=Path("data/skab"),
    file_type="csv",
    size_mb=15.0,
    license="MIT",
    citation="B. Trapeznikov et al., 'SKAB: Skoltech Anomaly Benchmark', 2021",
)

# NAB (Numenta Anomaly Benchmark)
NAB_SOURCE = DataSource(
    name="Numenta Anomaly Benchmark (NAB)",
    description="""
    58 labeled real-world and artificial time series with anomaly labels.
    Includes: AWS server metrics, Twitter volume, NYC taxi traffic, etc.
    Designed for evaluating anomaly detection in streaming data.
    """,
    url="https://github.com/numenta/NAB",
    local_path=Path("data/nab"),
    file_type="csv",
    size_mb=25.0,
    license="AGPL-3.0",
    citation="Ahmad et al., 'Unsupervised real-time anomaly detection for streaming data', Neurocomputing, 2017",
)

# SWaT (Secure Water Treatment)
SWAT_SOURCE = DataSource(
    name="SWaT Secure Water Treatment",
    description="""
    51 sensors and actuators from a water treatment testbed.
    7 days normal operation + 4 days with 36 cyber-physical attacks.
    Ground truth labels for attack detection research.
    """,
    url="https://itrust.sutd.edu.sg/itrust-labs_datasets_dataset_index/",
    local_path=Path("data/swat"),
    file_type="zip",
    size_mb=350.0,
    license="Research Use (requires registration)",
    citation="Goh et al., 'A Dataset to Support Research in the Design of Secure Water Treatment Systems', 2017",
)

ALL_SOURCES = [
    AI4I_SOURCE,
    NASA_BEARING_SOURCE,
    NASA_CMAPSS_SOURCE,
    SKAB_SOURCE,
    NAB_SOURCE,
    SWAT_SOURCE,
]


def download_source(source: DataSource, force: bool = False) -> Path:
    """Download a data source if not already present."""
    if source.local_path.exists() and not force:
        print(f"Using cached: {source.local_path}")
        return source.local_path

    source.local_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {source.name} from {source.url}...")

    if source.file_type == "zip":
        zip_path = source.local_path.with_suffix(".zip")
        urllib.request.urlretrieve(source.url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(source.local_path.parent)
        zip_path.unlink()
    else:
        urllib.request.urlretrieve(source.url, source.local_path)

    print(f"Downloaded to {source.local_path}")
    return source.local_path


def list_available_sources() -> list[dict[str, Any]]:
    """List all data sources with their availability status."""
    return [
        {
            "name": s.name,
            "description": s.description.strip(),
            "size_mb": s.size_mb,
            "license": s.license,
            "available": s.local_path.exists(),
            "local_path": str(s.local_path),
        }
        for s in ALL_SOURCES
    ]


def generate_mock_dataset(
    preset: str = "pump",
    scenario: str = "normal",
    num_rows: int = 1000,
    output_path: Path | None = None,
) -> Path:
    """Generate a mock dataset using the built-in generator."""
    from services.datasets.mock_generator import (
        ALL_PRESETS,
        MockGeneratorConfig,
        ScenarioState,
        ScenarioType,
        generate_csv,
    )

    if output_path is None:
        output_path = Path(f"data/mock_{preset}_{scenario}_{num_rows}.csv")

    config = MockGeneratorConfig(
        assets=ALL_PRESETS[preset],
        scenario=ScenarioState(ScenarioType(scenario)),
    )
    generate_csv(config, output_path, num_rows)
    return output_path


def main():
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Industrial data source catalog")
    parser.add_argument("--list", action="store_true", help="List all sources")
    parser.add_argument("--download", type=str, help="Download source by name")
    parser.add_argument("--generate-mock", action="store_true", help="Generate mock data")
    parser.add_argument("--preset", type=str, default="pump", choices=list(ALL_PRESETS.keys()))
    parser.add_argument("--scenario", type=str, default="normal")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("data/mock.csv"))
    args = parser.parse_args()

    if args.list:
        for source in list_available_sources():
            status = "✓" if source["available"] else "✗"
            print(f"{status} {source['name']} ({source['size_mb']} MB) - {source['license']}")
            print(f"   {source['description'][:100]}...")
    elif args.download:
        source = next((s for s in ALL_SOURCES if s.name.lower() == args.download.lower()), None)
        if source:
            download_source(source)
        else:
            print(f"Source not found: {args.download}")
            print("Available:", [s.name for s in ALL_SOURCES])
    elif args.generate_mock:
        path = generate_mock_dataset(args.preset, args.scenario, args.rows, args.output)
        print(f"Mock dataset generated: {path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

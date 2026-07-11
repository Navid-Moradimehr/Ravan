from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.datasets.runtime_catalog import list_dataset_sources
from services.common.training_dataset import validate_manifest


@dataclass(frozen=True)
class DatasetBuilderContract:
    contract_id: str
    description: str
    inputs: tuple[str, ...] = field(default_factory=tuple)
    outputs: tuple[str, ...] = field(default_factory=tuple)
    supported_purposes: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DATASET_BUILDER_CONTRACT = DatasetBuilderContract(
    contract_id="logical.dataset.builder",
    description="Curates versioned datasets for AI training, benchmarking, replay, and analytics without exposing raw historian data directly.",
    inputs=(
        "historian exports",
        "replay datasets",
        "scenario labels",
        "semantic metadata",
        "lineage metadata",
        "benchmark packs",
    ),
    outputs=(
        "curated dataset manifests",
        "versioned dataset slices",
        "license and provenance metadata",
        "benchmark-ready dataset bundles",
    ),
    supported_purposes=(
        "training",
        "benchmarking",
        "replay",
        "analytics",
    ),
    notes=(
        "This is a logical contract, not a new runtime service.",
        "Users remain responsible for their own storage and retention policy.",
        "The contract can later back a dataset-builder service or SDK.",
    ),
)


def build_dataset_builder_snapshot() -> dict[str, Any]:
    datasets = list_dataset_sources()
    curated = [
        {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "category": dataset.category,
            "best_use": dataset.best_use,
            "licensed": dataset.licensed,
            "curation_status": "available" if dataset.category in {"mock", "benchmark", "synthetic"} else "needs-validation",
        }
        for dataset in datasets
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plane": "logical-dataset-builder",
        "contract": DATASET_BUILDER_CONTRACT.to_dict(),
        "curated_datasets": curated,
        "dataset_count": len(curated),
        "contracts": {
            "logical_contract": True,
            "no_new_service": True,
            "curated_dataset_builder": True,
        },
        "notes": [
            "The builder is a logical contract that sits between lakehouse storage and AI workloads.",
            "Curated datasets should remain versioned and reproducible.",
            "Raw historian access remains a separate concern from dataset curation.",
            "Versioned training manifests are validated by services.common.training_dataset.",
        ],
    }

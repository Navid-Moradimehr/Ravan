from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.common.semantic_store import SemanticLineageRecord, get_semantic_store


@dataclass(frozen=True)
class LineageFacet:
    name: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LineageSummary:
    generated_at: str
    total_records: int
    by_kind: dict[str, int]
    by_site: dict[str, int]
    by_dataset: dict[str, int]
    by_model_version: dict[str, int]
    by_processing_version: dict[str, int]
    records: list[dict[str, Any]] = field(default_factory=list)
    openlineage_compatible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def lineage_record_to_openlineage(record: SemanticLineageRecord) -> dict[str, Any]:
    """Return a lightweight OpenLineage-style event payload.

    This is intentionally compatible in shape without pulling in the external
    service or SDK as a hard dependency.
    """
    run_id = record.lineage_id or record.source_id or record.entity_id or record.relationship_id
    job_name = record.kind or "lineage"
    namespace = record.site_id or "default"
    facets = {
        "source": LineageFacet("source_id", record.source_id).to_dict(),
        "site": LineageFacet("site_id", record.site_id).to_dict(),
        "dataset": LineageFacet("dataset_id", record.dataset_id).to_dict(),
        "model": LineageFacet("model_version", record.model_version).to_dict(),
        "processing": LineageFacet("processing_version", record.processing_version).to_dict(),
    }
    return {
        "eventType": "COMPLETE",
        "eventTime": record.occurred_at or datetime.now(timezone.utc).isoformat(),
        "producer": "datastream",
        "run": {"runId": run_id, "facets": {"site": facets["site"], "source": facets["source"]}},
        "job": {"namespace": namespace, "name": job_name},
        "inputs": [
            {
                "namespace": namespace,
                "name": record.source_id or record.dataset_id or record.entity_id or record.relationship_id or "unknown",
                "facets": {
                    "dataset": facets["dataset"],
                    "processing": facets["processing"],
                },
            }
        ]
        if record.source_id or record.dataset_id or record.entity_id or record.relationship_id
        else [],
        "outputs": [
            {
                "namespace": namespace,
                "name": record.target_id or record.entity_id or record.relationship_id or record.dataset_id or "unknown",
                "facets": {
                    "model": facets["model"],
                    "processing": facets["processing"],
                },
            }
        ],
        "facets": facets,
        "metadata": record.metadata,
    }


def build_lineage_snapshot(*, site_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    store = get_semantic_store()
    records = [SemanticLineageRecord(**record) for record in store.list_lineage(site_id=site_id, limit=limit)]
    by_kind = Counter(record.kind for record in records)
    by_site = Counter(record.site_id or "unspecified" for record in records)
    by_dataset = Counter(record.dataset_id or "unspecified" for record in records)
    by_model_version = Counter(record.model_version or "unspecified" for record in records)
    by_processing_version = Counter(record.processing_version or "unspecified" for record in records)

    return LineageSummary(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_records=len(records),
        by_kind=dict(by_kind),
        by_site=dict(by_site),
        by_dataset=dict(by_dataset),
        by_model_version=dict(by_model_version),
        by_processing_version=dict(by_processing_version),
        records=[
            {
                **record.to_dict(),
                "openlineage": lineage_record_to_openlineage(record),
            }
            for record in records
        ],
    ).to_dict()

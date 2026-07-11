"""Portable training-dataset manifest validation and local bundle compiler.

This is intentionally a library/CLI surface, not a training runtime. It can
consume exports from Iceberg, Kafka, TimescaleDB, or user-owned systems once
those records are exported to JSONL/CSV/Parquet.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONTROL_PURPOSES = {"dreamer", "muzero", "offline-control"}
SUPPORTED_PURPOSES = {"jepa", "dreamer", "muzero", "analytics", "benchmark"}
REQUIRED_MANIFEST_KEYS = {"dataset_id", "site_id", "time_range", "observation_sources", "purpose"}


@dataclass(frozen=True)
class DatasetValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "errors": list(self.errors), "warnings": list(self.warnings)}


def load_manifest(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("dataset manifest must contain a mapping")
    return payload


def validate_manifest(manifest: dict[str, Any]) -> DatasetValidation:
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(REQUIRED_MANIFEST_KEYS - set(manifest))
    errors.extend(f"missing required field: {key}" for key in missing)
    purpose = str(manifest.get("purpose", ""))
    if purpose and purpose not in SUPPORTED_PURPOSES:
        errors.append(f"purpose must be one of {sorted(SUPPORTED_PURPOSES)}")
    sources = manifest.get("observation_sources")
    if not isinstance(sources, list) or not sources:
        errors.append("observation_sources must be a non-empty list")
    alignment = manifest.get("alignment", {})
    if alignment and int(alignment.get("sample_interval_ms", 0) or 0) <= 0:
        errors.append("alignment.sample_interval_ms must be positive")
    if purpose in CONTROL_PURPOSES:
        if not manifest.get("action_sources"):
            errors.append(f"{purpose} datasets require action_sources")
        if not manifest.get("outcome_sources"):
            errors.append(f"{purpose} datasets require outcome_sources")
        if not manifest.get("episode_definition", {}).get("boundary"):
            errors.append(f"{purpose} datasets require episode_definition.boundary")
    if not manifest.get("provenance"):
        warnings.append("provenance is absent; reproducibility is incomplete")
    if not manifest.get("splits"):
        warnings.append("splits is absent; callers must define train/validation/test boundaries")
    return DatasetValidation(not errors, tuple(errors), tuple(warnings))


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else list(payload.get("records", []))
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_iceberg_sources(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Read explicitly selected Iceberg tables into bundle records.

    The config contains catalog/table locations only. Credentials are resolved
    from environment variables by the configured catalog client.
    """
    import pyiceberg.catalog

    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("iceberg source config must be a JSON object")
    catalog_config = {
        str(key): os.path.expandvars(str(value))
        for key, value in (config.get("catalog") or {}).items()
    }
    catalog_name = str(catalog_config.pop("name", "sql"))
    catalog = pyiceberg.catalog.load_catalog(catalog_name, **catalog_config)
    records: dict[str, list[dict[str, Any]]] = {}
    for logical_name, table_ref in (config.get("sources") or {}).items():
        namespace = str(table_ref.get("namespace", "industrial"))
        table_name = str(table_ref.get("table", logical_name))
        table = catalog.load_table((namespace, table_name))
        records[str(logical_name)] = table.scan().to_arrow().to_pylist()
    return records


def _write_parquet(path: Path, records: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(records) if records else pa.table({"record_count": pa.array([], type=pa.int64())})
    pq.write_table(table, path, compression="zstd")


def compile_bundle(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    observations: str | Path | None = None,
    operational_events: str | Path | None = None,
    outcomes: str | Path | None = None,
    iceberg_sources: str | Path | None = None,
    semantic_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    validation = validate_manifest(manifest)
    if not validation.valid:
        raise ValueError("invalid dataset manifest: " + "; ".join(validation.errors))
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    records_by_name: dict[str, list[dict[str, Any]]] = {}
    iceberg_records = _read_iceberg_sources(iceberg_sources) if iceberg_sources else {}
    for name, source in (
        ("observations", observations),
        ("operational_events", operational_events),
        ("outcomes", outcomes),
    ):
        records = iceberg_records.get(name)
        if records is None:
            records = _read_records(Path(source)) if source else []
        records_by_name[name] = records
        _write_parquet(destination / f"{name}.parquet", records)
    (destination / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (destination / "semantic_context.json").write_text(
        json.dumps(semantic_context or {}, indent=2, sort_keys=True), encoding="utf-8"
    )
    lineage = {
        "dataset_id": manifest["dataset_id"],
        "manifest_path": str(manifest_path),
        "source_files": {name: str(value) for name, value in (("observations", observations), ("operational_events", operational_events), ("outcomes", outcomes)) if value},
        "provenance": manifest.get("provenance", {}),
    }
    (destination / "lineage.json").write_text(json.dumps(lineage, indent=2, sort_keys=True), encoding="utf-8")
    quality = {
        "dataset_id": manifest["dataset_id"],
        "records": {name: len(records) for name, records in records_by_name.items()},
        "warnings": list(validation.warnings),
        "site_ids": sorted({str(record.get("site_id", record.get("site", ""))) for records in records_by_name.values() for record in records if record.get("site_id", record.get("site", ""))}),
    }
    (destination / "quality-report.json").write_text(json.dumps(quality, indent=2, sort_keys=True), encoding="utf-8")
    return {"dataset_id": manifest["dataset_id"], "output_dir": str(destination), "quality": quality, "validation": validation.to_dict()}

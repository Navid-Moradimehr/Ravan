"""Versioned dataset manifests and deterministic trajectory compilation.

This module prepares evidence for downstream JEPA, Dreamer, MuZero, or
classical training code. It deliberately does not train models, infer rewards,
interpolate missing telemetry, or execute actions.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from services.common.training_dataset import DatasetValidation, _read_records, validate_manifest


def manifest_version(manifest: dict[str, Any]) -> int:
    return int(manifest.get("manifest_version", manifest.get("schema_version", 1)) or 1)


def validate_model_manifest(manifest: dict[str, Any]) -> DatasetValidation:
    """Validate the v2 model-data manifest while retaining v1 compatibility."""

    if manifest_version(manifest) < 2:
        return validate_manifest(manifest)
    errors: list[str] = []
    warnings: list[str] = []
    for key in ("dataset_id", "site_ids", "time_range", "observation_sources", "purpose", "provenance"):
        if key not in manifest:
            errors.append(f"missing required field: {key}")
    purpose = str(manifest.get("purpose", ""))
    if purpose not in {"jepa", "dreamer", "muzero", "offline-control", "analytics", "benchmark"}:
        errors.append("purpose is not supported")
    site_ids = manifest.get("site_ids")
    if not isinstance(site_ids, list) or not site_ids or not all(str(site).strip() for site in site_ids):
        errors.append("site_ids must be a non-empty list")
    alignment = manifest.get("alignment") or {}
    interval = int(alignment.get("sample_interval_ms", 0) or 0)
    skew = int(alignment.get("max_skew_ms", -1) or -1)
    if interval <= 0:
        errors.append("alignment.sample_interval_ms must be positive")
    if skew < 0:
        errors.append("alignment.max_skew_ms must be zero or positive")
    observation_sources = manifest.get("observation_sources")
    if not observation_sources or not isinstance(observation_sources, (str, list, dict)):
        errors.append("observation_sources must be a non-empty path, mapping, or list")
    if purpose in {"dreamer", "muzero", "offline-control"}:
        if not manifest.get("action_sources"):
            errors.append(f"{purpose} datasets require action_sources")
        if not manifest.get("outcome_sources"):
            errors.append(f"{purpose} datasets require outcome_sources")
        if not (manifest.get("episode_definition") or {}).get("boundary"):
            errors.append(f"{purpose} datasets require episode_definition.boundary")
    if not manifest.get("splits"):
        warnings.append("splits is absent; train/test overlap must be checked by the consumer")
    if not manifest.get("semantic_context"):
        warnings.append("semantic_context is absent; topology context is incomplete")
    return DatasetValidation(not errors, tuple(errors), tuple(warnings))


def _source_records(source: Any) -> list[dict[str, Any]]:
    if isinstance(source, str):
        return _read_records(Path(source))
    if isinstance(source, list):
        return [dict(row) for row in source if isinstance(row, dict)]
    if isinstance(source, dict) and "path" in source:
        return _read_records(Path(str(source["path"])))
    return []


def _timestamp(record: dict[str, Any]) -> datetime | None:
    value = record.get("ts_source") or record.get("timestamp") or record.get("occurred_at") or record.get("effective_at") or record.get("observed_at") or record.get("time")
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except ValueError:
        return None


def _timestamp_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _nearest(records: list[dict[str, Any]], target_ms: int, max_skew_ms: int) -> dict[str, Any] | None:
    best: tuple[int, dict[str, Any]] | None = None
    for record in records:
        timestamp = _timestamp(record)
        if timestamp is None:
            continue
        distance = abs(_timestamp_ms(timestamp) - target_ms)
        if distance <= max_skew_ms and (best is None or distance < best[0]):
            best = (distance, record)
    return best[1] if best else None


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(rows) if rows else pa.table({"record_count": pa.array([], type=pa.int64())})
    pq.write_table(table, path, compression="zstd")


def _hash_manifest(manifest: dict[str, Any]) -> str:
    encoded = yaml.safe_dump(manifest, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compile_trajectory_bundle(manifest_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    manifest = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("model dataset manifest must be a mapping")
    validation = validate_model_manifest(manifest)
    if not validation.valid:
        raise ValueError("invalid model dataset manifest: " + "; ".join(validation.errors))
    if manifest_version(manifest) < 2:
        from services.common.training_dataset import compile_bundle

        return compile_bundle(manifest_path, output_dir)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    observation_records = _source_records(manifest.get("observation_sources"))
    action_records = _source_records(manifest.get("action_sources", []))
    outcome_records = _source_records(manifest.get("outcome_sources", []))
    artifact_records = _source_records(manifest.get("artifact_sources", []))
    interval = int(manifest["alignment"]["sample_interval_ms"])
    max_skew = int(manifest["alignment"]["max_skew_ms"])
    timed_observations = [(record, _timestamp(record)) for record in observation_records]
    timed_observations = [(record, ts) for record, ts in timed_observations if ts is not None]
    if not timed_observations:
        raise ValueError("observation_sources contains no parseable timestamps")
    start = min(ts for _, ts in timed_observations)
    end = max(ts for _, ts in timed_observations)
    channels = sorted({f"{record.get('asset_id', record.get('entity_id', 'unknown'))}::{record.get('tag', record.get('channel', 'value'))}" for record, _ in timed_observations})
    channel_records: dict[str, list[dict[str, Any]]] = {channel: [] for channel in channels}
    for record, _ in timed_observations:
        channel = f"{record.get('asset_id', record.get('entity_id', 'unknown'))}::{record.get('tag', record.get('channel', 'value'))}"
        channel_records[channel].append(record)
    steps: list[dict[str, Any]] = []
    cursor = _timestamp_ms(start)
    end_ms = _timestamp_ms(end)
    step_index = 0
    while cursor <= end_ms:
        values: list[float | None] = []
        mask: list[bool] = []
        for channel in channels:
            record = _nearest(channel_records[channel], cursor, max_skew)
            try:
                value = float(record.get("value")) if record is not None else None
                if value is not None and not math.isfinite(value):
                    value = None
            except (TypeError, ValueError):
                value = None
            values.append(value)
            mask.append(value is not None)
        steps.append({"step": step_index, "timestamp_ms": cursor, "observation_values": values, "observation_mask": mask})
        step_index += 1
        cursor += interval
    action_rows = [{"timestamp_ms": _timestamp_ms(ts), **record} for record in action_records if (ts := _timestamp(record)) is not None]
    outcome_rows = [{"timestamp_ms": _timestamp_ms(ts), **record} for record in outcome_records if (ts := _timestamp(record)) is not None]
    artifact_rows = [dict(record) for record in artifact_records]
    _write_parquet(destination / "steps.parquet", steps)
    _write_parquet(destination / "actions.parquet", action_rows)
    _write_parquet(destination / "outcomes.parquet", outcome_rows)
    _write_parquet(destination / "artifacts.parquet", artifact_rows)
    (destination / "channels.json").write_text(json.dumps({"channels": channels}, indent=2), encoding="utf-8")
    (destination / "semantic-context.json").write_text(json.dumps(manifest.get("semantic_context", {}), indent=2, sort_keys=True), encoding="utf-8")
    manifest_copy = dict(manifest)
    manifest_copy["manifest_hash"] = _hash_manifest(manifest)
    (destination / "manifest.yaml").write_text(yaml.safe_dump(manifest_copy, sort_keys=False), encoding="utf-8")
    lineage = {"dataset_id": manifest["dataset_id"], "manifest_hash": manifest_copy["manifest_hash"], "source_contract": "model-data-v2"}
    (destination / "lineage.json").write_text(json.dumps(lineage, indent=2, sort_keys=True), encoding="utf-8")
    quality = {
        "dataset_id": manifest["dataset_id"],
        "record_counts": {"observations": len(observation_records), "actions": len(action_rows), "outcomes": len(outcome_rows), "artifacts": len(artifact_rows), "steps": len(steps)},
        "missing_observation_values": sum(1 for row in steps for present in row["observation_mask"] if not present),
        "channels": len(channels),
        "warnings": list(validation.warnings),
        "gate_errors": [],
    }
    (destination / "quality-report.json").write_text(json.dumps(quality, indent=2, sort_keys=True), encoding="utf-8")
    (destination / "_SUCCESS").write_text("", encoding="utf-8")
    return {"dataset_id": manifest["dataset_id"], "output_dir": str(destination), "valid": True, "quality": quality, "manifest_hash": manifest_copy["manifest_hash"]}

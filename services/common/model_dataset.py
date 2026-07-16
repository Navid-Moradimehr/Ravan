"""Versioned dataset manifests and deterministic trajectory compilation.

This module prepares evidence for downstream JEPA, Dreamer, MuZero, or
classical training code. It deliberately does not train models, infer rewards,
interpolate missing telemetry, or execute actions.
"""

from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from services.common.training_dataset import DatasetValidation, _read_records, validate_manifest


def manifest_version(manifest: dict[str, Any]) -> int:
    return int(manifest.get("manifest_version", manifest.get("schema_version", 1)) or 1)


def validate_model_manifest(manifest: dict[str, Any]) -> DatasetValidation:
    """Validate model-data manifests while retaining v1/v2 compatibility."""

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
    if manifest_version(manifest) >= 3:
        if not (manifest.get("episode_definition") or {}).get("boundary"):
            errors.append("v3 datasets require episode_definition.boundary")
        splits = manifest.get("splits")
        if splits is not None and not isinstance(splits, dict):
            errors.append("splits must be a mapping when provided")
        elif isinstance(splits, dict) and splits.get("strategy") not in {None, "episode_hash", "temporal", "explicit"}:
            errors.append("splits.strategy must be episode_hash, temporal, or explicit")
        if not manifest.get("channel_identity"):
            warnings.append("channel_identity is absent; v3 defaults to site_id + entity_id + tag")
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


def _nearest_sorted(
    records: list[dict[str, Any]], timestamps_ms: list[int], target_ms: int, max_skew_ms: int
) -> dict[str, Any] | None:
    """Find the nearest record without rescanning the entire channel."""

    if not records:
        return None
    index = bisect_left(timestamps_ms, target_ms)
    candidates: list[tuple[int, int]] = []
    if index < len(records):
        candidates.append((abs(timestamps_ms[index] - target_ms), index))
    if index:
        candidates.append((abs(timestamps_ms[index - 1] - target_ms), index - 1))
    if not candidates:
        return None
    distance, selected = min(candidates, key=lambda item: (item[0], item[1]))
    return records[selected] if distance <= max_skew_ms else None


def _v3_identity(record: dict[str, Any]) -> tuple[str, str, str] | None:
    site_id = str(record.get("site_id", "")).strip()
    entity_id = str(record.get("asset_id", record.get("entity_id", ""))).strip()
    tag = str(record.get("tag", record.get("channel", ""))).strip()
    if not site_id or not entity_id or not tag:
        return None
    return site_id, entity_id, tag


def _v3_channel(identity: tuple[str, str, str]) -> str:
    return "::".join(identity)


def _episode_id(record: dict[str, Any]) -> str | None:
    for key in ("episode_id", "context_id", "lineage_id"):
        value = str(record.get(key, "")).strip()
        if value:
            return value
    return None


def _v3_split_assignments(episodes: list[str], splits: dict[str, Any] | None) -> dict[str, str]:
    """Assign whole episodes to deterministic, non-overlapping partitions."""

    configuration = dict(splits or {})
    strategy = str(configuration.get("strategy", "episode_hash"))
    if strategy == "explicit":
        assignments = configuration.get("assignments")
        if not isinstance(assignments, dict):
            raise ValueError("v3 explicit splits require splits.assignments")
        result = {episode: str(assignments.get(episode, "")) for episode in episodes}
        if any(value not in {"train", "validation", "test"} for value in result.values()):
            raise ValueError("v3 explicit splits must assign every episode to train, validation, or test")
        return result
    if strategy == "temporal":
        boundaries = configuration.get("boundaries")
        if not isinstance(boundaries, dict) or not boundaries.get("train_end") or not boundaries.get("validation_end"):
            raise ValueError("v3 temporal splits require boundaries.train_end and boundaries.validation_end")
        train_end = _timestamp_ms(_timestamp({"timestamp": boundaries["train_end"]}) or datetime.min.replace(tzinfo=timezone.utc))
        validation_end = _timestamp_ms(_timestamp({"timestamp": boundaries["validation_end"]}) or datetime.min.replace(tzinfo=timezone.utc))
        if validation_end <= train_end:
            raise ValueError("v3 temporal split boundaries must be increasing")
        result: dict[str, str] = {}
        episode_end_ms = configuration.get("episode_end_ms", {})
        for episode in episodes:
            end_ms = int(episode_end_ms.get(episode, -1)) if isinstance(episode_end_ms, dict) else -1
            if end_ms < 0:
                raise ValueError("v3 temporal split compilation requires episode_end_ms")
            if end_ms <= train_end:
                result[episode] = "train"
            elif end_ms <= validation_end:
                result[episode] = "validation"
            else:
                result[episode] = "test"
        return result
    if strategy != "episode_hash":
        raise ValueError(f"unsupported v3 split strategy: {strategy}")
    if len(episodes) < 3:
        raise ValueError("v3 episode_hash splits require at least three episodes; use explicit or temporal splits")
    ratios = configuration.get("ratios") or {"train": 0.7, "validation": 0.15, "test": 0.15}
    if not isinstance(ratios, dict):
        raise ValueError("v3 episode_hash splits.ratios must be a mapping")
    train_ratio = float(ratios.get("train", 0))
    validation_ratio = float(ratios.get("validation", 0))
    if train_ratio <= 0 or validation_ratio < 0 or train_ratio + validation_ratio >= 1:
        raise ValueError("v3 split ratios must leave a positive test partition")
    seed = str(configuration.get("seed", 0))
    result = {}
    for episode in episodes:
        bucket = int(hashlib.sha256(f"{seed}:{episode}".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        result[episode] = "train" if bucket < train_ratio else "validation" if bucket < train_ratio + validation_ratio else "test"
    return result


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pylist(rows) if rows else pa.table({"record_count": pa.array([], type=pa.int64())})
    pq.write_table(table, path, compression="zstd")


def _hash_manifest(manifest: dict[str, Any]) -> str:
    encoded = yaml.safe_dump(manifest, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _v3_value(record: dict[str, Any]) -> float | None:
    raw = record.get("value", record.get("observation_value"))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _compile_v3(
    manifest: dict[str, Any],
    destination: Path,
    validation: DatasetValidation,
) -> dict[str, Any]:
    """Compile a site-aware, episode-partitioned model-data bundle."""

    observation_records = _source_records(manifest.get("observation_sources"))
    action_records = _source_records(manifest.get("action_sources", []))
    outcome_records = _source_records(manifest.get("outcome_sources", []))
    artifact_records = _source_records(manifest.get("artifact_sources", []))
    interval = int(manifest["alignment"]["sample_interval_ms"])
    max_skew = int(manifest["alignment"]["max_skew_ms"])
    timed_observations = [(record, _timestamp(record)) for record in observation_records]
    timed_observations = [(record, timestamp) for record, timestamp in timed_observations if timestamp is not None]
    if not timed_observations:
        raise ValueError("observation_sources contains no parseable timestamps")

    invalid_identity = [record for record, _ in timed_observations if _v3_identity(record) is None]
    missing_episode = [record for record, _ in timed_observations if not _episode_id(record)]
    if invalid_identity:
        raise ValueError("v3 observations require site_id, asset_id/entity_id, and tag/channel")
    if missing_episode:
        raise ValueError("v3 observations require episode_id, context_id, or lineage_id")

    seen_event_ids: set[str] = set()
    duplicate_event_ids: set[str] = set()
    for record, _ in timed_observations:
        event_id = str(record.get("event_id", "")).strip()
        if event_id and event_id in seen_event_ids:
            duplicate_event_ids.add(event_id)
        elif event_id:
            seen_event_ids.add(event_id)
    if duplicate_event_ids:
        raise ValueError("v3 observations contain duplicate event_id values: " + ", ".join(sorted(duplicate_event_ids)[:5]))

    episode_groups: dict[tuple[str, str], list[tuple[dict[str, Any], datetime]]] = defaultdict(list)
    for record, timestamp in timed_observations:
        identity = _v3_identity(record)
        assert identity is not None
        episode_groups[(identity[0], _episode_id(record) or "")].append((record, timestamp))
    episode_keys = sorted(episode_groups)
    episode_ids = sorted({episode for _, episode in episode_keys})
    split_configuration = manifest.get("splits")
    if isinstance(split_configuration, dict) and split_configuration.get("strategy") == "temporal":
        split_configuration = dict(split_configuration)
        split_configuration["episode_end_ms"] = {
            episode: max(_timestamp_ms(timestamp) for records in episode_groups.values() for record, timestamp in records if _episode_id(record) == episode)
            for episode in episode_ids
        }
    split_by_episode = _v3_split_assignments(episode_ids, split_configuration)

    channels = sorted({_v3_channel(_v3_identity(record)) for record, _ in timed_observations if _v3_identity(record) is not None})
    channel_records: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record, _ in timed_observations:
        identity = _v3_identity(record)
        assert identity is not None
        channel_records[(_v3_channel(identity), _episode_id(record) or "")].append(record)
    channel_timestamps: dict[tuple[str, str], list[int]] = {}
    for channel_key, records in channel_records.items():
        records.sort(key=lambda record: _timestamp_ms(_timestamp(record) or datetime.min.replace(tzinfo=timezone.utc)))
        channel_timestamps[channel_key] = [_timestamp_ms(_timestamp(record) or datetime.min.replace(tzinfo=timezone.utc)) for record in records]

    steps: list[dict[str, Any]] = []
    steps_by_episode: dict[tuple[str, str], list[dict[str, Any]]] = {}
    step_index = 0
    for site_id, episode_id in episode_keys:
        records = episode_groups[(site_id, episode_id)]
        start_ms = min(_timestamp_ms(timestamp) for _, timestamp in records)
        end_ms = max(_timestamp_ms(timestamp) for _, timestamp in records)
        episode_steps: list[dict[str, Any]] = []
        cursor = start_ms
        while cursor <= end_ms:
            values: list[float | None] = []
            mask: list[bool] = []
            for channel in channels:
                channel_site = channel.split("::", 1)[0]
                channel_key = (channel, episode_id)
                record = (
                    _nearest_sorted(channel_records[channel_key], channel_timestamps[channel_key], cursor, max_skew)
                    if channel_site == site_id and channel_key in channel_records
                    else None
                )
                value = _v3_value(record) if record is not None else None
                values.append(value)
                mask.append(value is not None)
            step = {
                "step": step_index,
                "timestamp_ms": cursor,
                "site_id": site_id,
                "episode_id": episode_id,
                "split": split_by_episode[episode_id],
                "observation_values": values,
                "observation_mask": mask,
            }
            steps.append(step)
            episode_steps.append(step)
            step_index += 1
            cursor += interval
        steps_by_episode[(site_id, episode_id)] = episode_steps

    def event_rows(records: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for record in records:
            timestamp = _timestamp(record)
            identity = _v3_identity(record)
            episode_id = _episode_id(record)
            site_id = str(record.get("site_id", "")).strip() or (identity[0] if identity else "")
            if timestamp is None or not site_id or not episode_id:
                if record:
                    record_copy = dict(record)
                    record_copy["_invalid_reason"] = f"unlinked_{kind}"
                continue
            rows.append({
                "timestamp_ms": _timestamp_ms(timestamp),
                "site_id": site_id,
                "episode_id": episode_id,
                "split": split_by_episode.get(episode_id, "unassigned"),
                **record,
            })
        return rows

    action_rows = event_rows(action_records, "action")
    outcome_rows = event_rows(outcome_records, "outcome")
    artifact_rows = [dict(record) for record in artifact_records]
    transitions: list[dict[str, Any]] = []
    unlinked_actions = 0
    unlinked_outcomes = 0
    for (site_id, episode_id), episode_steps in steps_by_episode.items():
        episode_actions = [row for row in action_rows if row["site_id"] == site_id and row["episode_id"] == episode_id]
        episode_outcomes = [row for row in outcome_rows if row["site_id"] == site_id and row["episode_id"] == episode_id]
        action_times = [int(row["timestamp_ms"]) for row in episode_actions]
        outcome_times = [int(row["timestamp_ms"]) for row in episode_outcomes]
        for index, current in enumerate(episode_steps[:-1]):
            action = _nearest_sorted(episode_actions, action_times, current["timestamp_ms"], max_skew)
            outcome = _nearest_sorted(episode_outcomes, outcome_times, current["timestamp_ms"], max_skew)
            if action is None:
                unlinked_actions += 1
            if outcome is None:
                unlinked_outcomes += 1
            transitions.append({
                "step": current["step"],
                "next_step": episode_steps[index + 1]["step"],
                "timestamp_ms": current["timestamp_ms"],
                "next_timestamp_ms": episode_steps[index + 1]["timestamp_ms"],
                "site_id": site_id,
                "episode_id": episode_id,
                "split": current["split"],
                "action_id": action.get("action_id") if action else None,
                "outcome_id": outcome.get("outcome_id") if outcome else None,
                "reward": outcome.get("reward") if outcome else None,
                "terminal": bool(outcome.get("terminal", False)) if outcome else False,
                "observation_values": current["observation_values"],
                "next_observation_values": episode_steps[index + 1]["observation_values"],
                "observation_mask": current["observation_mask"],
                "next_observation_mask": episode_steps[index + 1]["observation_mask"],
            })

    channel_metadata: dict[str, dict[str, Any]] = {}
    channel_records_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (channel, _episode_id_value), records in channel_records.items():
        channel_records_by_id[channel].extend(records)
    for channel, records in channel_records_by_id.items():
        units = sorted({str(record.get("unit", record.get("units", ""))).strip() for record in records if record.get("unit", record.get("units"))})
        if len(units) > 1:
            raise ValueError(f"v3 channel {channel} changes units: {units}")
        channel_metadata[channel] = {
            "site_id": channel.split("::", 1)[0],
            "entity_id": channel.split("::")[1],
            "tag": channel.split("::", 2)[2],
            "unit": units[0] if units else None,
            "calibration_versions": sorted({str(record.get("calibration_version")) for record in records if record.get("calibration_version")}),
            "topology_versions": sorted({str(record.get("topology_version")) for record in records if record.get("topology_version")}),
        }

    destination.mkdir(parents=True, exist_ok=True)
    _write_parquet(destination / "steps.parquet", steps)
    _write_parquet(destination / "actions.parquet", action_rows)
    _write_parquet(destination / "outcomes.parquet", outcome_rows)
    _write_parquet(destination / "transitions.parquet", transitions)
    _write_parquet(destination / "artifacts.parquet", artifact_rows)
    (destination / "channels.json").write_text(json.dumps({"channels": channels, "channel_metadata": channel_metadata}, indent=2, sort_keys=True), encoding="utf-8")
    (destination / "semantic-context.json").write_text(json.dumps(manifest.get("semantic_context", {}), indent=2, sort_keys=True), encoding="utf-8")
    manifest_copy = dict(manifest)
    manifest_copy["manifest_version"] = 3
    manifest_copy["effective_splits"] = {"strategy": (split_configuration or {}).get("strategy", "episode_hash"), "assignments": split_by_episode}
    manifest_copy["manifest_hash"] = _hash_manifest(manifest_copy)
    (destination / "manifest.yaml").write_text(yaml.safe_dump(manifest_copy, sort_keys=False), encoding="utf-8")
    lineage = {"dataset_id": manifest["dataset_id"], "manifest_hash": manifest_copy["manifest_hash"], "source_contract": "model-data-v3", "episodes": len(episode_ids), "splits": split_by_episode}
    (destination / "lineage.json").write_text(json.dumps(lineage, indent=2, sort_keys=True), encoding="utf-8")
    quality = {
        "dataset_id": manifest["dataset_id"],
        "record_counts": {"observations": len(observation_records), "actions": len(action_rows), "outcomes": len(outcome_rows), "artifacts": len(artifact_rows), "steps": len(steps), "transitions": len(transitions), "episodes": len(episode_ids)},
        "missing_observation_values": sum(1 for row in steps for present in row["observation_mask"] if not present),
        "channels": len(channels),
        "episode_splits": {split: sum(1 for value in split_by_episode.values() if value == split) for split in ("train", "validation", "test")},
        "unlinked_actions": unlinked_actions,
        "unlinked_outcomes": unlinked_outcomes,
        "warnings": list(validation.warnings),
        "gate_errors": [],
    }
    (destination / "quality-report.json").write_text(json.dumps(quality, indent=2, sort_keys=True), encoding="utf-8")
    (destination / "_SUCCESS").write_text("", encoding="utf-8")
    return {"dataset_id": manifest["dataset_id"], "output_dir": str(destination), "valid": True, "quality": quality, "manifest_hash": manifest_copy["manifest_hash"]}


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
    if manifest_version(manifest) >= 3:
        return _compile_v3(manifest, destination, validation)
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

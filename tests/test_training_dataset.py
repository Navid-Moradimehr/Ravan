from __future__ import annotations

import json
from pathlib import Path

import yaml

from services.common.training_dataset import compile_bundle, validate_manifest


def _manifest(purpose: str = "jepa") -> dict:
    payload = {
        "dataset_id": "plant-a-jepa-v1",
        "site_id": "plant-a",
        "time_range": "2026-01-01/2026-02-01",
        "observation_sources": ["industrial.normalized"],
        "purpose": purpose,
        "alignment": {"sample_interval_ms": 1000},
        "provenance": {"mapping_version": "source-a:v3"},
    }
    if purpose in {"dreamer", "muzero"}:
        payload.update({"action_sources": ["industrial.operational"], "outcome_sources": ["mes.outcomes"], "episode_definition": {"boundary": "batch_id"}})
    return payload


def test_control_manifest_requires_actions_and_outcomes() -> None:
    result = validate_manifest(_manifest("dreamer"))
    assert result.valid
    invalid = validate_manifest({**_manifest("dreamer"), "action_sources": []})
    assert not invalid.valid


def test_compile_bundle_writes_portable_artifacts(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    observations = tmp_path / "observations.jsonl"
    observations.write_text(json.dumps({"event_id": "e1", "site_id": "plant-a", "value": 42}) + "\n", encoding="utf-8")
    result = compile_bundle(manifest_path, tmp_path / "bundle", observations=observations)
    assert result["quality"]["records"]["observations"] == 1
    assert (tmp_path / "bundle" / "observations.parquet").exists()
    assert (tmp_path / "bundle" / "lineage.json").exists()


def test_iceberg_reader_is_optional_and_does_not_change_file_path(tmp_path: Path) -> None:
    # The source config is only consumed when explicitly passed; ordinary
    # file-backed compilation remains the default path.
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    observations = tmp_path / "observations.jsonl"
    observations.write_text(json.dumps({"event_id": "e1", "site_id": "plant-a"}) + "\n", encoding="utf-8")
    result = compile_bundle(manifest_path, tmp_path / "bundle", observations=observations)
    assert result["quality"]["records"]["observations"] == 1

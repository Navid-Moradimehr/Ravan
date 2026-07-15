from __future__ import annotations

import json

import yaml

from services.common.model_dataset import compile_trajectory_bundle, validate_model_manifest


def _manifest(observations: str, actions: str, outcomes: str) -> dict:
    return {
        "manifest_version": 2,
        "dataset_id": "plant-a-pump-trajectory-v1",
        "site_ids": ["plant-a"],
        "time_range": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:02Z"},
        "purpose": "dreamer",
        "observation_sources": observations,
        "action_sources": actions,
        "outcome_sources": outcomes,
        "episode_definition": {"boundary": "industrial.boundary.v1"},
        "alignment": {"sample_interval_ms": 1000, "max_skew_ms": 100},
        "provenance": {"source": "simulated-pump"},
        "semantic_context": {"asset": "pump-1", "unit": "bar"},
    }


def test_v2_manifest_requires_bounded_alignment():
    result = validate_model_manifest({"manifest_version": 2, "dataset_id": "x"})
    assert not result.valid
    assert any("alignment.sample_interval_ms" in error for error in result.errors)


def test_compile_trajectory_bundle_aligns_without_interpolation(tmp_path):
    observations = tmp_path / "observations.jsonl"
    observations.write_text(
        "\n".join(
            [
                json.dumps({"event_id": "o1", "site_id": "plant-a", "asset_id": "pump-1", "tag": "pressure", "value": 4.2, "timestamp": "2026-01-01T00:00:00Z"}),
                json.dumps({"event_id": "o2", "site_id": "plant-a", "asset_id": "pump-1", "tag": "pressure", "value": 4.4, "timestamp": "2026-01-01T00:00:02Z"}),
            ]
        ),
        encoding="utf-8",
    )
    actions = tmp_path / "actions.jsonl"
    actions.write_text(json.dumps({"action_id": "a1", "command": "speed", "applied_value": 20, "occurred_at": "2026-01-01T00:00:01Z"}), encoding="utf-8")
    outcomes = tmp_path / "outcomes.jsonl"
    outcomes.write_text(json.dumps({"outcome_id": "r1", "metric": "yield", "value": 0.9, "observed_at": "2026-01-01T00:00:02Z"}), encoding="utf-8")
    manifest = _manifest(str(observations), str(actions), str(outcomes))
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    result = compile_trajectory_bundle(manifest_path, tmp_path / "bundle")

    assert result["valid"] is True
    assert (tmp_path / "bundle" / "_SUCCESS").exists()
    assert json.loads((tmp_path / "bundle" / "quality-report.json").read_text())["record_counts"]["steps"] == 3
    assert json.loads((tmp_path / "bundle" / "channels.json").read_text())["channels"] == ["pump-1::pressure"]

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
    assert json.loads((tmp_path / "bundle" / "quality-report.json").read_text())["record_counts"]["outcomes"] == 1
    assert json.loads((tmp_path / "bundle" / "channels.json").read_text())["channels"] == ["pump-1::pressure"]


def test_v3_preserves_site_identity_and_emits_episode_transitions(tmp_path):
    observations = tmp_path / "observations-v3.jsonl"
    rows = []
    for site_id, episode_id in (("plant-a", "episode-a"), ("plant-b", "episode-b"), ("plant-c", "episode-c")):
        for second, value in enumerate((4.0, 4.5, 5.0)):
            rows.append(
                json.dumps(
                    {
                        "event_id": f"{site_id}-o-{second}",
                        "site_id": site_id,
                        "asset_id": "pump-1",
                        "tag": "pressure",
                        "unit": "bar",
                        "episode_id": episode_id,
                        "value": value,
                        "timestamp": f"2026-01-01T00:00:0{second}Z",
                    }
                )
            )
    observations.write_text("\n".join(rows), encoding="utf-8")
    actions = tmp_path / "actions-v3.jsonl"
    actions.write_text(
        "\n".join(
            json.dumps({"action_id": f"{episode_id}-a", "site_id": site_id, "episode_id": episode_id, "command": "speed", "occurred_at": "2026-01-01T00:00:01Z"})
            for site_id, episode_id in (("plant-a", "episode-a"), ("plant-b", "episode-b"), ("plant-c", "episode-c"))
        ),
        encoding="utf-8",
    )
    outcomes = tmp_path / "outcomes-v3.jsonl"
    outcomes.write_text(
        "\n".join(
            json.dumps({"outcome_id": f"{episode_id}-r", "site_id": site_id, "episode_id": episode_id, "reward": 0.9, "observed_at": "2026-01-01T00:00:02Z"})
            for site_id, episode_id in (("plant-a", "episode-a"), ("plant-b", "episode-b"), ("plant-c", "episode-c"))
        ),
        encoding="utf-8",
    )
    manifest = {
        "manifest_version": 3,
        "dataset_id": "multi-site-v3",
        "site_ids": ["plant-a", "plant-b", "plant-c"],
        "time_range": {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:00:02Z"},
        "purpose": "dreamer",
        "observation_sources": str(observations),
        "action_sources": str(actions),
        "outcome_sources": str(outcomes),
        "episode_definition": {"boundary": "industrial.boundary.v1"},
        "alignment": {"sample_interval_ms": 1000, "max_skew_ms": 100},
        "splits": {"strategy": "explicit", "assignments": {"episode-a": "train", "episode-b": "validation", "episode-c": "test"}},
        "provenance": {"source": "simulated-multi-site"},
        "semantic_context": {"asset": "pump-1", "unit": "bar"},
    }
    manifest_path = tmp_path / "manifest-v3.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")

    result = compile_trajectory_bundle(manifest_path, tmp_path / "bundle-v3")

    assert result["valid"] is True
    quality = json.loads((tmp_path / "bundle-v3" / "quality-report.json").read_text())
    assert quality["record_counts"] == {"observations": 9, "actions": 3, "outcomes": 3, "artifacts": 0, "steps": 9, "transitions": 6, "episodes": 3}
    assert quality["episode_splits"] == {"train": 1, "validation": 1, "test": 1}
    channels = json.loads((tmp_path / "bundle-v3" / "channels.json").read_text())
    assert channels["channels"] == ["plant-a::pump-1::pressure", "plant-b::pump-1::pressure", "plant-c::pump-1::pressure"]
    assert "transitions.parquet" in {path.name for path in (tmp_path / "bundle-v3").iterdir()}


def test_v3_hash_splits_require_enough_episodes(tmp_path):
    manifest = _manifest("observations.jsonl", "actions.jsonl", "outcomes.jsonl")
    manifest["manifest_version"] = 3
    result = validate_model_manifest(manifest)
    assert result.valid
    observations = tmp_path / "observations.jsonl"
    observations.write_text(json.dumps({"event_id": "o1", "site_id": "plant-a", "asset_id": "pump-1", "tag": "pressure", "episode_id": "only", "value": 1, "timestamp": "2026-01-01T00:00:00Z"}), encoding="utf-8")
    manifest["observation_sources"] = str(observations)
    manifest["action_sources"] = []
    manifest["outcome_sources"] = []
    manifest["purpose"] = "jepa"
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    try:
        compile_trajectory_bundle(path, tmp_path / "bundle")
    except ValueError as error:
        assert "at least three episodes" in str(error)
    else:
        raise AssertionError("expected v3 split validation to reject one episode")

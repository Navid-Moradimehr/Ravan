from __future__ import annotations

from pathlib import Path

import pytest

from services.common.site_profiles import load_site_profile, validate_site_profile

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_single_site_profile():
    profile = load_site_profile(REPO_ROOT / "config" / "site-profiles" / "single-site.yaml")
    assert profile.profile_id == "single-site-demo"
    assert profile.site.id == "demo-site"
    assert profile.deployment_mode == "single-site"
    assert profile.runtime.mode == "python-fallback"
    assert profile.to_env()["SEMANTIC_STORE_BACKEND"] == "auto"
    assert profile.backups.owner == "plant-ops"
    assert profile.backups.restore_drill_owner == "qa-ops"
    assert profile.to_env()["DATASTREAM_BACKUP_OWNER"] == "plant-ops"
    assert profile.to_env()["DATASTREAM_RESTORE_DRILL_OWNER"] == "qa-ops"


def test_plant_local_profile_sets_db_backed_semantic_store():
    profile = load_site_profile(REPO_ROOT / "config" / "site-profiles" / "plant-local.yaml")
    assert profile.to_env()["SEMANTIC_STORE_BACKEND"] == "db"
    assert profile.backups.owner == "plant-a-ops"


def test_federated_profile_sets_db_backed_semantic_store():
    profile = load_site_profile(REPO_ROOT / "config" / "site-profiles" / "federated.yaml")
    assert profile.to_env()["SEMANTIC_STORE_BACKEND"] == "db"
    assert profile.backups.restore_drill_owner == "qa-ops"


def test_federated_profile_requires_endpoint(tmp_path):
    path = tmp_path / "bad-profile.yaml"
    path.write_text(
        """
schema_version: 1
profile_id: bad-fed
deployment_mode: federated
site:
  id: plant-x
  name: Plant X
  region: test
  network_zone: ops
runtime:
  image_tag: latest
  redpanda_brokers: localhost:9092
  historian_backend: timescaledb
  ai:
    provider: disabled
    endpoint_url: ""
    model_id: ""
    local_only: true
backups:
  directory: backups/x
  schedule: daily
  retention_days: 7
federation:
  enabled: true
  export_mode: rollup
        """.strip(),
        encoding="utf-8",
    )
    profile = load_site_profile(path)
    errors = validate_site_profile(profile)
    assert any("central_endpoint" in error for error in errors)


def test_runtime_mode_validation_rejects_unknown_mode(tmp_path):
    path = tmp_path / "bad-mode.yaml"
    path.write_text(
        """
schema_version: 1
profile_id: bad-mode
deployment_mode: single-site
site:
  id: demo
  name: Demo
  region: test
  network_zone: ops
runtime:
  image_tag: latest
  mode: invalid-mode
  redpanda_brokers: localhost:9092
  historian_backend: timescaledb
  ai:
    provider: disabled
    endpoint_url: ""
    model_id: ""
    local_only: true
backups:
  directory: backups/demo
  schedule: daily
  retention_days: 7
federation:
  enabled: false
  export_mode: none
        """.strip(),
        encoding="utf-8",
    )
    profile = load_site_profile(path)
    errors = validate_site_profile(profile)
    assert any("runtime.mode" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

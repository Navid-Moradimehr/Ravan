from __future__ import annotations

from pathlib import Path

from services.common.project_manifest import load_project_manifest, validate_project_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "config" / "project-manifest.yaml"


def test_load_project_manifest():
    manifest = load_project_manifest(MANIFEST)
    assert manifest.project_id == "demo-industrial-fleet"
    assert len(manifest.sites) == 2
    assert len(manifest.sources) == 3
    assert Path(manifest.sites[0].profile_path).as_posix().endswith("site-profiles/single-site.yaml")


def test_validate_project_manifest():
    manifest = load_project_manifest(MANIFEST)
    errors = validate_project_manifest(manifest)
    assert errors == []


def test_manifest_exports_site_envs():
    manifest = load_project_manifest(MANIFEST)
    envs = manifest.to_site_envs()
    assert "demo-site" in envs
    assert envs["demo-site"]["DATASTREAM_PROJECT_ID"] == "demo-industrial-fleet"
    assert envs["plant-a"]["SITE_ID"] == "plant-a"

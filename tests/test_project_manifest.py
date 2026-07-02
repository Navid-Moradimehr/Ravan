from __future__ import annotations

from dataclasses import replace
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


def test_manifest_source_site_map():
    manifest = load_project_manifest(MANIFEST)
    site_map = manifest.source_site_map()
    assert site_map["plc-01-pump-temp"] == "demo-site"
    assert site_map["line-a-pump-vibration"] == "plant-a"


def test_manifest_export_bundles(tmp_path: Path):
    manifest = load_project_manifest(MANIFEST)
    written = manifest.export_bundles(tmp_path, site_id="demo-site", fmt="both")
    assert len(written) == 2
    env_path = tmp_path / "demo-site.env"
    yaml_path = tmp_path / "demo-site.yaml"
    assert env_path.exists()
    assert yaml_path.exists()
    assert "DATASTREAM_PROJECT_ID=demo-industrial-fleet" in env_path.read_text(encoding="utf-8")
    assert "site_id: demo-site" in yaml_path.read_text(encoding="utf-8")


def test_manifest_export_systemd_layout(tmp_path: Path):
    manifest = load_project_manifest(MANIFEST)
    written = manifest.export_bundles(tmp_path, site_id="demo-site", fmt="both", layout="systemd")
    site_root = tmp_path / "demo-site"
    assert site_root.exists()
    assert (site_root / "env" / "site.env").exists()
    assert (site_root / "site-profile.yaml").exists()
    assert (site_root / "bundle.yaml").exists()
    assert (site_root / "systemd" / "datastreamd.service").exists()
    assert (site_root / "systemd" / "README.md").exists()
    assert (site_root / "systemd" / "install.sh").exists()
    assert (site_root / "systemd" / "uninstall.sh").exists()
    assert any(path.name == "datastreamd.service" for path in written)


def test_manifest_export_kubernetes_layout(tmp_path: Path):
    manifest = load_project_manifest(MANIFEST)
    written = manifest.export_bundles(tmp_path, site_id="plant-a", fmt="both", layout="kubernetes")
    site_root = tmp_path / "plant-a"
    assert site_root.exists()
    assert (site_root / "env" / "site.env").exists()
    assert (site_root / "site-profile.yaml").exists()
    assert (site_root / "kubernetes" / "configmap.yaml").exists()
    assert (site_root / "kubernetes" / "site-profile-configmap.yaml").exists()
    assert (site_root / "kubernetes" / "deployment.yaml").exists()
    assert (site_root / "kubernetes" / "service.yaml").exists()
    assert (site_root / "kubernetes" / "kustomization.yaml").exists()
    assert "namespaceOverride: datastream-plant-a" in (site_root / "kubernetes" / "helm" / "values.generated.yaml").read_text(encoding="utf-8")
    assert (site_root / "kubernetes" / "README.md").exists()
    assert any(path.name == "deployment.yaml" for path in written)


def test_manifest_package_export(tmp_path: Path):
    manifest = load_project_manifest(MANIFEST)
    written = manifest.export_package(tmp_path, site_id="demo-site", fmt="both")
    site_root = tmp_path / "demo-site"
    assert site_root.exists()
    assert (site_root / "flat" / "site.env").exists()
    assert (site_root / "flat" / "bundle.yaml").exists()
    assert (site_root / "systemd" / "install.sh").exists()
    assert (site_root / "kubernetes" / "helm" / "install.sh").exists()
    assert (site_root / "README.md").exists()
    assert any(path.name == "site.env" for path in written)


def test_manifest_lint_flags_collisions():
    manifest = load_project_manifest(MANIFEST)
    issues = manifest.lint()
    assert issues == []


def test_manifest_lint_detects_topic_collision():
    manifest = load_project_manifest(MANIFEST)
    colliding = replace(
        manifest,
        sources=manifest.sources + (
            replace(manifest.sources[0], source_id="duplicate-source", topic=manifest.sources[0].topic),
        ),
    )
    issues = colliding.lint()
    assert any("topic collision" in issue for issue in issues)


def test_validate_project_manifest_requires_source_site_id():
    manifest = load_project_manifest(MANIFEST)
    broken = replace(
        manifest,
        sources=manifest.sources + (
            replace(manifest.sources[0], source_id="floating-source", site_id=""),
        ),
    )
    errors = validate_project_manifest(broken)
    assert any("site_id is required" in error for error in errors)


def test_validate_project_manifest_requires_site_boundary_in_topic():
    manifest = load_project_manifest(MANIFEST)
    broken = replace(
        manifest,
        sources=manifest.sources + (
            replace(
                manifest.sources[0],
                source_id="site-less-topic",
                topic="industrial/shared/line-01/site-less-topic",
            ),
        ),
    )
    errors = validate_project_manifest(broken)
    assert any("topic must include site boundary" in error for error in errors)


def test_validate_project_manifest_requires_explicit_cross_site_correlation_strategy():
    manifest = load_project_manifest(MANIFEST)
    broken = replace(
        manifest,
        correlation_groups=manifest.correlation_groups
        + (
            replace(
                manifest.correlation_groups[0],
                name="cross-site-correlation",
                members=(manifest.sources[0].source_id, manifest.sources[-1].source_id),
                strategy="site_asset_tag",
            ),
        ),
    )
    errors = validate_project_manifest(broken)
    assert any("cross-site grouping requires explicit cross_site or federated strategy" in error for error in errors)

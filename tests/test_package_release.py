from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package-release.py"
_SPEC = importlib.util.spec_from_file_location("package_release", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_ignore_generated = _MODULE._ignore_generated
build_compose = _MODULE.build_compose
build_kubernetes = _MODULE.build_kubernetes
verify_bundle = _MODULE.verify_bundle


def test_release_package_excludes_development_artifacts() -> None:
    ignored = _ignore_generated("ui", ["target", "playwright-smoke.cjs", "next-dev.log", "docs", "page.tsx"])
    assert {"target", "playwright-smoke.cjs", "next-dev.log", "docs"}.issubset(ignored)
    assert "page.tsx" not in ignored


def test_release_package_excludes_tests_and_vault() -> None:
    ignored = _ignore_generated(".", ["tests", "ObsidianVault", "docs", "services"])
    assert {"tests", "ObsidianVault"}.issubset(ignored)
    assert "docs" not in ignored


def test_compose_target_contains_runtime_and_public_docs(tmp_path: Path) -> None:
    result = build_compose(
        _MODULE.DEFAULT_MANIFEST,
        tmp_path,
        "demo-site",
        "both",
        False,
        "DATASTREAM_RELEASE_SIGNING_KEY",
        "none",
    )
    root = Path(result["stage_root"])
    assert (root / "runtime" / "docker" / "docker-compose.yml").exists()
    assert (root / "runtime" / "docs" / "self-host-install-guide.md").exists()
    assert (root / "site" / "demo-site.env").exists()
    assert not (root / "runtime" / "tests").exists()
    assert not (root / "runtime" / "ObsidianVault").exists()


def test_kubernetes_target_contains_chart_and_generated_site_bundle(tmp_path: Path) -> None:
    result = build_kubernetes(
        _MODULE.DEFAULT_MANIFEST,
        tmp_path,
        "demo-site",
        "both",
        False,
        "DATASTREAM_RELEASE_SIGNING_KEY",
        "none",
    )
    root = Path(result["stage_root"])
    assert (root / "k8s" / "helm" / "Chart.yaml").exists()
    assert (root / "runtime" / "docs" / "flink-operator-runbook.md").exists()
    assert (root / "site" / "demo-site" / "kubernetes" / "helm" / "values.generated.yaml").exists()
    assert not (root / "runtime" / "tests").exists()
    assert not (root / "runtime" / "ObsidianVault").exists()


def test_verify_accepts_a_valid_compose_bundle(tmp_path: Path) -> None:
    result = build_compose(
        _MODULE.DEFAULT_MANIFEST,
        tmp_path,
        "demo-site",
        "both",
        False,
        "DATASTREAM_RELEASE_SIGNING_KEY",
        "none",
    )
    verification = verify_bundle(Path(result["stage_root"]), "compose")
    assert verification["valid"] is True
    assert verification["errors"] == []


def test_verify_rejects_development_and_secret_artifacts(tmp_path: Path) -> None:
    result = build_compose(
        _MODULE.DEFAULT_MANIFEST,
        tmp_path,
        "demo-site",
        "both",
        False,
        "DATASTREAM_RELEASE_SIGNING_KEY",
        "none",
    )
    root = Path(result["stage_root"])
    (root / "runtime" / "tests").mkdir()
    (root / "runtime" / "tests" / "test_secret.py").write_text("", encoding="utf-8")
    (root / "runtime" / ".env").write_text("SECRET=value\n", encoding="utf-8")

    verification = verify_bundle(root, "compose")

    assert verification["valid"] is False
    assert any("development artifact" in error for error in verification["errors"])
    assert any("secret file" in error for error in verification["errors"])

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "package-release.py"
_SPEC = importlib.util.spec_from_file_location("package_release", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_ignore_generated = _MODULE._ignore_generated


def test_release_package_excludes_development_artifacts() -> None:
    ignored = _ignore_generated("ui", ["target", "playwright-smoke.cjs", "next-dev.log", "docs", "page.tsx"])
    assert {"target", "playwright-smoke.cjs", "next-dev.log", "docs"}.issubset(ignored)
    assert "page.tsx" not in ignored


def test_release_package_excludes_tests_and_vault() -> None:
    ignored = _ignore_generated(".", ["tests", "ObsidianVault", "docs", "services"])
    assert {"tests", "ObsidianVault"}.issubset(ignored)
    assert "docs" not in ignored

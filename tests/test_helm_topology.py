from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "k8s" / "helm"


pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="helm is not installed")


def _template(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["helm", "template", "test", str(CHART), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_default_chart_has_one_processor_and_core_fanouts() -> None:
    result = _template()
    assert result.returncode == 0, result.stderr
    assert 'RUNTIME_MODE: "python-fallback"' in result.stdout
    assert result.stdout.count("component: processor") >= 2
    for component in ("normalized-fanout", "processed-fanout", "ai-fanout"):
        assert f"component: {component}" in result.stdout


def test_flink_mode_requires_python_processor_disabled() -> None:
    result = _template("--set", "env.RUNTIME_MODE=flink-production")
    assert result.returncode != 0
    assert "processor.enabled must be false" in result.stderr


def test_edge_horizontal_scaling_is_rejected() -> None:
    result = _template("--set", "edgeIngest.replicaCount=2")
    assert result.returncode != 0
    assert "edgeIngest.replicaCount must remain 1" in result.stderr

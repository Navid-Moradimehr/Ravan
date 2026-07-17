from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_release_evidence.py"
SPEC = importlib.util.spec_from_file_location("release_evidence", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_release_evidence_contains_artifact_hashes_and_runtime_dependencies(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "ravan.zip").write_bytes(b"release")
    output_dir = tmp_path / "evidence"

    checksums, sbom, provenance = MODULE.generate(ROOT, artifact_dir, output_dir, "1.0.0-beta.1")

    assert "ravan.zip" in checksums.read_text(encoding="utf-8")
    sbom_payload = json.loads(sbom.read_text(encoding="utf-8"))
    assert sbom_payload["spdxVersion"] == "SPDX-2.3"
    assert any(item["name"] == "fastapi" for item in sbom_payload["packages"])
    provenance_payload = json.loads(provenance.read_text(encoding="utf-8"))
    assert provenance_payload["subject"][0]["name"] == "ravan.zip"

#!/usr/bin/env python3
"""Generate deterministic checksums, a lightweight SBOM, and provenance evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def requirements(root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    path = root / "requirements.txt"
    if not path.is_file():
        return entries
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name, _, version = line.partition("==")
        entries.append({"name": name, "version": version or "unspecified"})
    return entries


def generate(root: Path, artifact_dir: Path, output_dir: Path, version: str) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = sorted(path for path in artifact_dir.glob("*") if path.is_file())
    checksums = output_dir / "checksums.sha256"
    checksums.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in artifacts),
        encoding="utf-8",
    )
    sbom = output_dir / "ravan-sbom.spdx.json"
    packages = requirements(root)
    sbom.write_text(json.dumps({
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"ravan-{version}",
        "documentNamespace": f"https://github.com/Navid-Moradimehr/Ravan/releases/{version}/sbom",
        "creationInfo": {"created": datetime.now(timezone.utc).isoformat(), "creators": ["Tool: Ravan release evidence"]},
        "packages": [
            {"SPDXID": f"SPDXRef-Package-{item['name']}", "name": item["name"], "versionInfo": item["version"], "downloadLocation": "NOASSERTION"}
            for item in packages
        ],
    }, indent=2), encoding="utf-8")
    provenance = output_dir / "release-provenance.json"
    provenance.write_text(json.dumps({
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": path.name, "digest": {"sha256": sha256(path)}} for path in artifacts],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildType": "github-actions-or-local-release-script",
            "version": version,
            "sourceRevision": git_revision(root),
            "builder": "Ravan release evidence generator",
            "platform": platform.platform(),
        },
    }, indent=2), encoding="utf-8")
    return checksums, sbom, provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    files = generate(args.root.resolve(), args.artifact_dir.resolve(), args.output_dir.resolve(), args.version)
    print(json.dumps([str(path) for path in files], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

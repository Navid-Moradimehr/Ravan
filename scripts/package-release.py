#!/usr/bin/env python3
"""Stage repo-based release packages for Windows, Linux, and offline installs.

This script is intentionally thin: it reuses the existing project-manifest
exports and copies the runtime source tree that already exists in the repo.

Modes:
    windows  - native Windows host package
    linux    - native Linux/systemd host package
    offline  - air-gapped source bundle plus docs and sample data
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import tarfile
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from services.common.project_manifest import load_project_manifest, validate_project_manifest

DEFAULT_MANIFEST = REPO_ROOT / "config" / "project-manifest.yaml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist"
RUNTIME_COPY_DIRS = ("services", "config", "scripts", "ui", "rust")
RUNTIME_COPY_FILES = ("README.md", "pyproject.toml", "requirements.txt")
OFFLINE_EXTRA_DIRS = ("data",)
OFFLINE_EXTRA_FILES = (
    "docs/self-host-install-guide.md",
    "docs/deployment-decision-memo.md",
    "docs/release-packaging-checklist.md",
    "docs/phase8-distribution.md",
    "services/ingestion/debezium-postgres-orders.json",
)
IGNORE_NAMES = {"__pycache__", ".git", ".venv", "node_modules", ".next", "dist", "build", "coverage"}


def _ignore_generated(_: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in IGNORE_NAMES:
            ignored.add(name)
        elif name.endswith((".pyc", ".pyo")):
            ignored.add(name)
        elif fnmatch.fnmatch(name, "*.egg-info"):
            ignored.add(name)
    return ignored


def _copy_file(src: Path, dst: Path) -> list[Path]:
    if not src.exists():
        return []
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return [dst]


def _copy_dir(src: Path, dst: Path) -> list[Path]:
    if not src.exists():
        return []
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore_generated)
    return [path for path in dst.rglob("*") if path.is_file()]


def _archive_dir(root: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
                zf.write(file_path, file_path.relative_to(root.parent))
    elif archive_path.suffixes[-2:] == [".tar", ".gz"]:
        with tarfile.open(archive_path, "w:gz") as tf:
            tf.add(root, arcname=root.name)
    else:
        raise ValueError(f"unsupported archive format: {archive_path.name}")
    return archive_path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    return path


def _copy_runtime_tree(stage_root: Path, include_docs: bool) -> list[Path]:
    written: list[Path] = []
    for entry in RUNTIME_COPY_DIRS:
        src = REPO_ROOT / entry
        if src.exists():
            written.extend(_copy_dir(src, stage_root / entry))
    for entry in RUNTIME_COPY_FILES:
        src = REPO_ROOT / entry
        if src.exists():
            written.extend(_copy_file(src, stage_root / entry))
    if include_docs:
        for entry in OFFLINE_EXTRA_DIRS:
            src = REPO_ROOT / entry
            if src.exists():
                written.extend(_copy_dir(src, stage_root / entry))
        for entry in OFFLINE_EXTRA_FILES:
            src = REPO_ROOT / entry
            if src.exists():
                written.extend(_copy_file(src, stage_root / entry))
    return written


def _export_site_bundle(manifest, stage_root: Path, site_id: str, layout: str, fmt: str, sign: bool, signing_key_env: str) -> list[Path]:
    written: list[Path] = []
    written.extend(manifest.export_bundles(stage_root / "site", site_id=site_id, fmt=fmt, layout=layout))
    signing_key = os.getenv(signing_key_env) if sign else None
    if sign and not signing_key:
        raise ValueError(f"{signing_key_env} is required when --sign is set")
    written.extend(
        manifest.export_release_artifact(
            stage_root / "release",
            site_id=site_id,
            fmt=fmt,
            signing_key=signing_key,
            signing_key_id=signing_key_env,
        )
    )
    return written


def _finalize_bundle(stage_root: Path, archive_format: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "stage_root": str(stage_root),
        "file_count": sum(1 for path in stage_root.rglob("*") if path.is_file()),
        "archive": None,
        "archive_sha256": None,
    }
    if archive_format == "none":
        return payload
    if archive_format == "zip":
        archive_path = stage_root.parent / f"{stage_root.name}.zip"
    elif archive_format == "tar.gz":
        archive_path = stage_root.parent / f"{stage_root.name}.tar.gz"
    else:
        raise ValueError(f"unsupported archive format: {archive_format}")
    _archive_dir(stage_root, archive_path)
    payload["archive"] = str(archive_path)
    payload["archive_sha256"] = _sha256(archive_path)
    return payload


def build_windows(manifest_path: Path, output_dir: Path, site_id: str, fmt: str, sign: bool, signing_key_env: str, archive_format: str) -> dict[str, object]:
    manifest = load_project_manifest(manifest_path)
    errors = validate_project_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    stage_root = output_dir / f"{site_id}-windows"
    shutil.rmtree(stage_root, ignore_errors=True)
    written = _copy_runtime_tree(stage_root / "runtime", include_docs=False)
    written.extend(_export_site_bundle(manifest, stage_root, site_id, layout="windows", fmt=fmt, sign=sign, signing_key_env=signing_key_env))
    written.append(_write_json(stage_root / "package-manifest.json", {
        "mode": "windows",
        "site_id": site_id,
        "manifest": str(manifest_path),
        "written": [str(path.relative_to(stage_root)) for path in written],
    }))
    payload = _finalize_bundle(stage_root, archive_format)
    payload.update({"mode": "windows", "site_id": site_id, "manifest": str(manifest_path)})
    _write_json(stage_root / "release-summary.json", payload)
    return payload


def build_linux(manifest_path: Path, output_dir: Path, site_id: str, fmt: str, sign: bool, signing_key_env: str, archive_format: str) -> dict[str, object]:
    manifest = load_project_manifest(manifest_path)
    errors = validate_project_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    stage_root = output_dir / f"{site_id}-linux"
    shutil.rmtree(stage_root, ignore_errors=True)
    written = _copy_runtime_tree(stage_root / "runtime", include_docs=False)
    written.extend(_export_site_bundle(manifest, stage_root, site_id, layout="systemd", fmt=fmt, sign=sign, signing_key_env=signing_key_env))
    written.append(_write_json(stage_root / "package-manifest.json", {
        "mode": "linux",
        "site_id": site_id,
        "manifest": str(manifest_path),
        "written": [str(path.relative_to(stage_root)) for path in written],
    }))
    payload = _finalize_bundle(stage_root, archive_format)
    payload.update({"mode": "linux", "site_id": site_id, "manifest": str(manifest_path)})
    _write_json(stage_root / "release-summary.json", payload)
    return payload


def build_offline(manifest_path: Path, output_dir: Path, site_id: str, fmt: str, sign: bool, signing_key_env: str, archive_format: str) -> dict[str, object]:
    manifest = load_project_manifest(manifest_path)
    errors = validate_project_manifest(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    stage_root = output_dir / f"{site_id}-offline"
    shutil.rmtree(stage_root, ignore_errors=True)
    written = _copy_runtime_tree(stage_root / "runtime", include_docs=True)
    written.extend(_export_site_bundle(manifest, stage_root, site_id, layout="package", fmt=fmt, sign=sign, signing_key_env=signing_key_env))
    written.append(_write_json(stage_root / "package-manifest.json", {
        "mode": "offline",
        "site_id": site_id,
        "manifest": str(manifest_path),
        "written": [str(path.relative_to(stage_root)) for path in written],
    }))
    payload = _finalize_bundle(stage_root, archive_format)
    payload.update({"mode": "offline", "site_id": site_id, "manifest": str(manifest_path)})
    _write_json(stage_root / "release-summary.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage repo-based packaging outputs for Windows, Linux, and offline installs.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--site-id", default="demo-site")
    parser.add_argument("--format", choices=["env", "yaml", "both"], default="both")
    parser.add_argument("--sign", action="store_true")
    parser.add_argument("--signing-key-env", default="DATASTREAM_RELEASE_SIGNING_KEY")
    parser.add_argument("--archive", choices=["zip", "tar.gz", "none"], default="zip")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("windows", help="Stage a native Windows package")
    sub.add_parser("linux", help="Stage a native Linux package")
    sub.add_parser("offline", help="Stage an offline bundle")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "windows":
        payload = build_windows(args.manifest, args.output_dir, args.site_id, args.format, args.sign, args.signing_key_env, args.archive)
    elif args.mode == "linux":
        payload = build_linux(args.manifest, args.output_dir, args.site_id, args.format, args.sign, args.signing_key_env, args.archive)
    elif args.mode == "offline":
        payload = build_offline(args.manifest, args.output_dir, args.site_id, args.format, args.sign, args.signing_key_env, args.archive)
    else:
        raise ValueError(f"unknown mode: {args.mode}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

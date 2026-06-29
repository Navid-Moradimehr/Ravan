"""datastream-import - download, validate, and stage testing datasets.

Part of the Phase 8 distribution surface. Fetches real/synthetic
industrial datasets into a local data directory, validates them against
the platform's canonical shape, and reports what is ready to replay.

Usage:
    datastream-import list
    datastream-import fetch ai4i
    datastream-import fetch ai4i --out data/ai4i2020.csv
    datastream-import info ai4i
    datastream-import validate data/ai4i2020.csv --format ai4i
    datastream-import status
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = Path(os.getenv("DATASTREAM_DATA_DIR", PROJECT_ROOT / "data"))


@dataclass(frozen=True)
class ImportSource:
    source_id: str
    name: str
    category: str
    format: str
    url: str
    filename: str
    size_note: str
    license_note: str
    licensed: bool


SOURCES: tuple[ImportSource, ...] = (
    ImportSource(
        source_id="ai4i",
        name="AI4I 2020 Predictive Maintenance",
        category="synthetic",
        format="csv",
        url="https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip",
        filename="ai4i2020.csv",
        size_note="~1.5 MB",
        license_note="CC BY 4.0",
        licensed=True,
    ),
    ImportSource(
        source_id="cmapss",
        name="NASA C-MAPSS turbofan degradation",
        category="synthetic",
        format="zip",
        url="https://data.nasa.gov/download/ff5e-badge/ZIP",
        filename="cmAPSS.zip",
        size_note="~45 MB",
        license_note="NASA Open Data (US Gov public domain)",
        licensed=True,
    ),
    ImportSource(
        source_id="nab",
        name="Numenta Anomaly Benchmark",
        category="industrial",
        format="zip",
        url="https://github.com/numenta/NAB/archive/refs/heads/master.zip",
        filename="nab.zip",
        size_note="~25 MB",
        license_note="AGPL-3.0",
        licensed=True,
    ),
    ImportSource(
        source_id="skab",
        name="Skoltech Anomaly Benchmark (SKAB)",
        category="industrial",
        format="csv",
        url="https://raw.githubusercontent.com/waico/SKAB/master/data/anomalies/0.csv",
        filename="skab.csv",
        size_note="~15 MB",
        license_note="MIT",
        licensed=True,
    ),
)

SOURCE_BY_ID = {s.source_id: s for s in SOURCES}


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _http_download(url: str, dest: Path, timeout: float = 30.0) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "datastream-import/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            out.write(chunk)


def _extract_csv_from_zip(zip_path: Path, out_dir: Path) -> list[Path]:
    import zipfile

    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if member.lower().endswith(".csv"):
                target = out_dir / Path(member).name
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted.append(target)
    return extracted


def _load_runtime_catalog():
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from services.datasets.runtime_catalog import get_dataset_source

        return get_dataset_source
    except Exception:
        return None


def cmd_list(args: argparse.Namespace) -> int:
    print("datastream-import sources")
    print("=" * 64)
    for s in SOURCES:
        present = (DEFAULT_DATA_DIR / s.filename).exists() if args.check else False
        marker = "[present]" if present else ""
        print(f"{s.source_id:<10}{s.name}  {marker}")
        print(f"{'':10}format={s.format}  size={s.size_note}  license={s.license_note}")
        print(f"{'':10}url={s.url}")
        print()
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    src = SOURCE_BY_ID.get(args.source_id)
    if not src:
        print(f"unknown source: {args.source_id}; choices: {list(SOURCE_BY_ID)}")
        return 2
    get_catalog = _load_runtime_catalog()
    catalog_meta = get_catalog(src.source_id) if get_catalog else None
    print(f"{src.name}")
    print("=" * 64)
    for key in ("source_id", "category", "format", "filename", "size_note", "license_note", "licensed"):
        print(f"{key:<14}{getattr(src, key)}")
    print(f"{'url':<14}{src.url}")
    if catalog_meta:
        print(f"{'signals':<14}{catalog_meta.signals}")
        print(f"{'best_use':<14}{catalog_meta.best_use}")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    src = SOURCE_BY_ID.get(args.source_id)
    if not src:
        print(f"unknown source: {args.source_id}; choices: {list(SOURCE_BY_ID)}")
        return 2

    _ensure_dir(DEFAULT_DATA_DIR)
    dest = DEFAULT_DATA_DIR / src.filename
    local = Path(args.out) if args.out else dest

    if local.exists() and not args.force:
        print(f"[{src.source_id}] already present at {local} (use --force to re-download)")
        return 0

    if args.local:
        if not Path(args.local).exists():
            print(f"[{src.source_id}] local source not found: {args.local}")
            return 1
        import shutil

        shutil.copyfile(args.local, local)
        print(f"[{src.source_id}] staged from local {args.local} -> {local}")
        return 0

    print(f"[{src.source_id}] downloading {src.url} -> {local}")
    try:
        _http_download(src.url, local, timeout=args.timeout)
    except Exception as exc:
        print(f"[{src.source_id}] download failed: {exc}")
        print(f"[{src.source_id}] you can stage the file manually: datastream-import fetch {src.source_id} --local <path>")
        return 1

    digest = _file_sha256(local)
    print(f"[{src.source_id}] saved {local} sha256={digest[:16]}...")

    if src.format == "zip" and args.extract:
        extracted = _extract_csv_from_zip(local, DEFAULT_DATA_DIR)
        if extracted:
            print(f"[{src.source_id}] extracted CSVs:")
            for p in extracted:
                print(f"  - {p}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"file not found: {path}")
        return 1

    fmt = args.format
    sys.path.insert(0, str(PROJECT_ROOT))

    if fmt == "ai4i":
        from services.datasets.ai4i_adapter import map_ai4i_row, read_ai4i_rows

        rows = read_ai4i_rows(path)
        if not rows:
            print(f"no rows parsed from {path}")
            return 1
        events = map_ai4i_row(rows[0], "validation-machine")
        tags = {e["tag"] for e in events}
        expected = {"AirTemperature", "ProcessTemperature", "RotationalSpeed", "Torque", "ToolWear"}
        ok = expected <= tags
        status = "OK" if ok else "MISMATCH"
        print(f"{status:<8}ai4i rows={len(rows)} tags={sorted(tags)}")
        if not ok:
            missing = expected - tags
            print(f"        missing expected tags: {missing}")
        return 0 if ok else 1

    print(f"unsupported format: {fmt} (supported: ai4i)")
    return 2


def cmd_status(args: argparse.Namespace) -> int:
    print("datastream-import status")
    print("=" * 64)
    _ensure_dir(DEFAULT_DATA_DIR)
    present = []
    for s in SOURCES:
        local = DEFAULT_DATA_DIR / s.filename
        exists = local.exists()
        size = local.stat().st_size if exists else 0
        marker = "OK " if exists else "-- "
        print(f"{marker}{s.source_id:<10}{s.filename:<24}{size:>10} bytes")
        if exists:
            present.append(s.source_id)
    print()
    print(f"present={len(present)}/{len(SOURCES)} data_dir={DEFAULT_DATA_DIR}")
    if args.json:
        print(json.dumps({"present": present, "data_dir": str(DEFAULT_DATA_DIR)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datastream-import",
        description="Download, validate, and stage testing datasets.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    lst = sub.add_parser("list", help="List known import sources")
    lst.add_argument("--check", action="store_true", help="Mark sources already present locally")
    lst.set_defaults(func=cmd_list)

    info = sub.add_parser("info", help="Show details for one source")
    info.add_argument("source_id")
    info.set_defaults(func=cmd_info)

    fetch = sub.add_parser("fetch", help="Download or stage a dataset")
    fetch.add_argument("source_id")
    fetch.add_argument("--out", default=None, help="Output path (default: data/<filename>)")
    fetch.add_argument("--force", action="store_true", help="Re-download even if present")
    fetch.add_argument("--local", default=None, help="Stage from a local file instead of downloading")
    fetch.add_argument("--extract", action="store_true", help="Extract CSVs from zip sources")
    fetch.add_argument("--timeout", type=float, default=30.0)
    fetch.set_defaults(func=cmd_fetch)

    val = sub.add_parser("validate", help="Validate a staged dataset against the canonical shape")
    val.add_argument("path")
    val.add_argument("--format", default="ai4i", choices=["ai4i"])
    val.set_defaults(func=cmd_validate)

    status = sub.add_parser("status", help="Show which datasets are staged locally")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

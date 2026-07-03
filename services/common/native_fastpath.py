from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


_EXT_SUFFIXES = {".pyd", ".so", ".dll"}


@lru_cache(maxsize=1)
def load_native_fastpath() -> Any | None:
    if os.getenv("DATASTREAM_NATIVE_FASTPATH", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return None

    root = Path(__file__).resolve().parents[2] / "rust" / "fastpath" / "target"
    if not root.exists():
        return None

    candidates = []
    for build_dir in ("release", "debug"):
        base = root / build_dir
        if not base.exists():
            continue
        for path in base.rglob("fastpath*"):
            if path.suffix.lower() in _EXT_SUFFIXES:
                candidates.append(path)

    for path in candidates:
        loader = importlib.machinery.ExtensionFileLoader("fastpath", str(path))
        spec = importlib.util.spec_from_loader("fastpath", loader, origin=str(path))
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            return module
        except Exception:
            continue
    return None


def json_bytes(payload: Any) -> bytes | None:
    module = load_native_fastpath()
    if module is None:
        return None
    try:
        return module.json_bytes(payload)
    except Exception:
        return None


def stream_partition_key(payload: Any) -> bytes | None:
    module = load_native_fastpath()
    if module is None:
        return None
    try:
        return module.stream_partition_key(payload)
    except Exception:
        return None


def encode_event_bundle(payload: Any) -> tuple[bytes, bytes, bytes] | None:
    module = load_native_fastpath()
    if module is None:
        return None
    try:
        return module.encode_event_bundle(payload)
    except Exception:
        return None

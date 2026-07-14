"""Safe, operator-controlled release checks.

This module deliberately stops at release metadata.  Replacing a running
industrial deployment belongs to an installer/update agent with signing,
drain, backup, migration, health-check, and rollback support.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx


_VERSION_RE = re.compile(r"^(?:v)?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?$")


def current_version() -> str:
    try:
        return version("local-stream-engine")
    except PackageNotFoundError:
        return "0.3.0"


def version_key(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.match(value.strip())
    if not match:
        raise ValueError(f"unsupported release version: {value!r}")
    return tuple(int(part or 0) for part in match.groups())


@dataclass(frozen=True)
class UpdateCheckResult:
    enabled: bool
    current_version: str
    latest_version: str | None
    available: bool
    checked_at: str | None
    release_url: str | None = None
    notes_url: str | None = None
    artifact_url: str | None = None
    sha256: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _disabled(current: str, reason: str | None = None) -> UpdateCheckResult:
    return UpdateCheckResult(
        enabled=False,
        current_version=current,
        latest_version=None,
        available=False,
        checked_at=None,
        error=reason,
    )


def check_for_update(
    *,
    manifest_url: str | None = None,
    enabled: bool | None = None,
    current: str | None = None,
    timeout_seconds: float = 3.0,
    client: httpx.Client | None = None,
) -> UpdateCheckResult:
    current = current or current_version()
    if enabled is None:
        enabled = os.getenv("DATASTREAM_UPDATE_CHECK_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    manifest_url = manifest_url or os.getenv("DATASTREAM_UPDATE_MANIFEST_URL", "").strip()
    if not enabled:
        return _disabled(current)
    if not manifest_url:
        return _disabled(current, "update checks are enabled but DATASTREAM_UPDATE_MANIFEST_URL is empty")

    owns_client = client is None
    client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
    try:
        response = client.get(manifest_url, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        latest = str(payload.get("version", "")).strip()
        version_key(latest)
        current_key = version_key(current)
        latest_key = version_key(latest)
        return UpdateCheckResult(
            enabled=True,
            current_version=current,
            latest_version=latest,
            available=latest_key > current_key,
            checked_at=datetime.now(timezone.utc).isoformat(),
            release_url=payload.get("release_url"),
            notes_url=payload.get("notes_url"),
            artifact_url=payload.get("artifact_url"),
            sha256=payload.get("sha256"),
        )
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        return UpdateCheckResult(
            enabled=True,
            current_version=current,
            latest_version=None,
            available=False,
            checked_at=datetime.now(timezone.utc).isoformat(),
            error=str(exc),
        )
    finally:
        if owns_client:
            client.close()

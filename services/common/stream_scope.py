from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import os
from typing import Any

try:  # pragma: no cover - optional compiled fast path
    import datastream_fastpath
except ImportError:  # pragma: no cover - extension not installed
    datastream_fastpath = None

FASTPATH_DISABLED = os.getenv("DATASTREAM_DISABLE_FASTPATH", "").lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class StreamScope:
    site: str
    line: str
    source_protocol: str
    source_id: str
    asset_id: str
    tag: str
    project_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_stream_scope(event: dict[str, Any] | Any) -> StreamScope:
    if isinstance(event, dict):
        get = event.get
        return StreamScope(
            site=str(get("site") or get("site_id") or "demo-site"),
            line=str(get("line") or get("line_id") or "line-01"),
            source_protocol=str(get("source_protocol") or "unknown"),
            source_id=str(get("source_id") or get("plc_id") or get("device_id") or get("asset_id") or "unknown-source"),
            asset_id=str(get("asset_id") or get("device_id") or "unknown-asset"),
            tag=str(get("tag") or "unknown"),
            project_id=str(get("project_id") or get("site") or get("site_id") or ""),
        )

    if hasattr(event, "model_dump"):
        data = event.model_dump(mode="json")
    elif is_dataclass(event):
        data = asdict(event)
    else:
        data = dict(event)
    return StreamScope(
        site=str(data.get("site") or data.get("site_id") or "demo-site"),
        line=str(data.get("line") or data.get("line_id") or "line-01"),
        source_protocol=str(data.get("source_protocol") or "unknown"),
        source_id=str(data.get("source_id") or data.get("plc_id") or data.get("device_id") or data.get("asset_id") or "unknown-source"),
        asset_id=str(data.get("asset_id") or data.get("device_id") or "unknown-asset"),
        tag=str(data.get("tag") or "unknown"),
        project_id=str(data.get("project_id") or data.get("site") or data.get("site_id") or ""),
    )


def stream_partition_key(event: dict[str, Any] | Any) -> bytes:
    if not FASTPATH_DISABLED and datastream_fastpath is not None:
        try:
            return datastream_fastpath.stream_partition_key_from_event(event)
        except Exception:
            pass
    if isinstance(event, dict):
        get = event.get
        return "|".join(
            [
                str(get("project_id") or get("site") or get("site_id") or ""),
                str(get("site") or get("site_id") or "demo-site"),
                str(get("line") or get("line_id") or "line-01"),
                str(get("source_protocol") or "unknown"),
                str(get("source_id") or get("plc_id") or get("device_id") or get("asset_id") or "unknown-source"),
                str(get("asset_id") or get("device_id") or "unknown-asset"),
                str(get("tag") or "unknown"),
            ]
        ).encode("utf-8")

    scope = derive_stream_scope(event)
    return "|".join(
        [
            scope.project_id,
            scope.site,
            scope.line,
            scope.source_protocol,
            scope.source_id,
            scope.asset_id,
            scope.tag,
        ]
    ).encode("utf-8")


def correlation_group_key(event: dict[str, Any] | Any) -> str:
    if isinstance(event, dict):
        get = event.get
        return "|".join(
            [
                str(get("project_id") or get("site") or get("site_id") or ""),
                str(get("site") or get("site_id") or "demo-site"),
                str(get("asset_id") or get("device_id") or "unknown-asset"),
                str(get("tag") or "unknown"),
            ]
        )

    if hasattr(event, "model_dump"):
        data = event.model_dump(mode="json")
    elif is_dataclass(event):
        data = asdict(event)
    else:
        data = dict(event)
    return "|".join(
        [
            str(data.get("project_id") or data.get("site") or data.get("site_id") or ""),
            str(data.get("site") or data.get("site_id") or "demo-site"),
            str(data.get("asset_id") or data.get("device_id") or "unknown-asset"),
            str(data.get("tag") or "unknown"),
        ]
    )

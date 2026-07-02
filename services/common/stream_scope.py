from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


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
    scope = derive_stream_scope(event)
    key = "|".join(
        [
            scope.project_id,
            scope.site,
            scope.line,
            scope.source_protocol,
            scope.source_id,
            scope.asset_id,
            scope.tag,
        ]
    )
    return key.encode("utf-8")


def correlation_group_key(event: dict[str, Any] | Any) -> str:
    scope = derive_stream_scope(event)
    return "|".join([scope.project_id, scope.site, scope.asset_id, scope.tag])

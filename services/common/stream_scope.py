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
    return StreamScope(
        site=str(_first_event_value(event, "site", "site_id", default="demo-site")),
        line=str(_first_event_value(event, "line", "line_id", default="line-01")),
        source_protocol=str(_first_event_value(event, "source_protocol", default="unknown")),
        source_id=str(
            _first_event_value(
                event,
                "source_id",
                "plc_id",
                "device_id",
                "asset_id",
                default="unknown-source",
            )
        ),
        asset_id=str(_first_event_value(event, "asset_id", "device_id", default="unknown-asset")),
        tag=str(_first_event_value(event, "tag", default="unknown")),
        project_id=str(_first_event_value(event, "project_id", "site", "site_id", default="")),
    )


def stream_partition_key(event: dict[str, Any] | Any) -> bytes:
    key = "|".join(
        [
            str(_first_event_value(event, "project_id", "site", "site_id", default="")),
            str(_first_event_value(event, "site", "site_id", default="demo-site")),
            str(_first_event_value(event, "line", "line_id", default="line-01")),
            str(_first_event_value(event, "source_protocol", default="unknown")),
            str(_first_event_value(event, "source_id", "plc_id", "device_id", "asset_id", default="unknown-source")),
            str(_first_event_value(event, "asset_id", "device_id", default="unknown-asset")),
            str(_first_event_value(event, "tag", default="unknown")),
        ]
    )
    return key.encode("utf-8")


def correlation_group_key(event: dict[str, Any] | Any) -> str:
    return "|".join(
        [
            str(_first_event_value(event, "project_id", "site", "site_id", default="")),
            str(_first_event_value(event, "site", "site_id", default="demo-site")),
            str(_first_event_value(event, "asset_id", "device_id", default="unknown-asset")),
            str(_first_event_value(event, "tag", default="unknown")),
        ]
    )


def _first_event_value(event: dict[str, Any] | Any, *names: str, default: Any) -> Any:
    if isinstance(event, dict):
        for name in names:
            value = event.get(name)
            if value:
                return value
        return default

    if hasattr(event, "model_dump"):
        for name in names:
            value = getattr(event, name, None)
            if value:
                return value
        return default

    if is_dataclass(event):
        data = asdict(event)
        for name in names:
            value = data.get(name)
            if value:
                return value
        return default

    for name in names:
        value = getattr(event, name, None)
        if value:
            return value
    return default

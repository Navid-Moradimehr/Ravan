"""CRUD operations for assets model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# In-memory store (replace with database in production)
_assets_db: dict[str, dict[str, Any]] = {}


@dataclass
class AssetNode:
    id: str
    name: str
    type: str
    parent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "tags": self.tags,
        }


def add_asset(asset: AssetNode) -> None:
    _assets_db[asset.id] = asset.to_dict()


def get_asset(asset_id: str) -> AssetNode | None:
    data = _assets_db.get(asset_id)
    if not data:
        return None
    return AssetNode(**data)


def update_asset(asset_id: str, **kwargs) -> AssetNode | None:
    if asset_id not in _assets_db:
        return None
    _assets_db[asset_id].update(kwargs)
    return AssetNode(**_assets_db[asset_id])


def delete_asset(asset_id: str) -> bool:
    if asset_id in _assets_db:
        del _assets_db[asset_id]
        return True
    return False


def add_tag_to_asset(
    asset_id: str,
    tag_id: str,
    name: str,
    unit: str,
    min_val: float,
    max_val: float,
    warning_low: float | None = None,
    warning_high: float | None = None,
    critical_low: float | None = None,
    critical_high: float | None = None,
    sampling_rate_hz: float = 1.0,
) -> dict[str, Any] | None:
    if asset_id not in _assets_db:
        return None
    tag = {
        "id": tag_id,
        "name": name,
        "unit": unit,
        "min": min_val,
        "max": max_val,
        "warning_low": warning_low,
        "warning_high": warning_high,
        "critical_low": critical_low,
        "critical_high": critical_high,
        "sampling_rate_hz": sampling_rate_hz,
    }
    _assets_db[asset_id]["tags"].append(tag)
    return tag

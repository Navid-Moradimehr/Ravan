from __future__ import annotations

import json
import os
from services.common.cache import ttl_cache
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TagMetadata:
    id: str
    name: str
    unit: str
    min: float
    max: float
    warning_low: float
    warning_high: float
    critical_low: float
    critical_high: float
    sampling_rate_hz: float

    def severity_for(self, value: float) -> str:
        if value <= self.critical_low or value >= self.critical_high:
            return "critical"
        if value <= self.warning_low or value >= self.warning_high:
            return "warning"
        return "normal"


@dataclass
class Asset:
    id: str
    name: str
    type: str
    tags: dict[str, TagMetadata] = field(default_factory=dict)


@dataclass
class Cell:
    id: str
    name: str
    assets: dict[str, Asset] = field(default_factory=dict)


@dataclass
class Line:
    id: str
    name: str
    cells: dict[str, Cell] = field(default_factory=dict)


@dataclass
class Area:
    id: str
    name: str
    lines: dict[str, Line] = field(default_factory=dict)


@dataclass
class Site:
    id: str
    name: str
    areas: dict[str, Area] = field(default_factory=dict)


@dataclass
class AssetHierarchy:
    sites: dict[str, Site] = field(default_factory=dict)

    def tag_for(self, asset_id: str, tag_name: str) -> TagMetadata | None:
        for site in self.sites.values():
            for area in site.areas.values():
                for line in area.lines.values():
                    for cell in line.cells.values():
                        asset = cell.assets.get(asset_id)
                        if asset:
                            return asset.tags.get(f"{asset_id}.{tag_name}")
        return None

    def all_tags(self) -> list[TagMetadata]:
        tags: list[TagMetadata] = []
        for site in self.sites.values():
            for area in site.areas.values():
                for line in area.lines.values():
                    for cell in line.cells.values():
                        for asset in cell.assets.values():
                            tags.extend(asset.tags.values())
        return tags

    def to_semantic_graph(self, source_uri: str | None = None):
        from services.common.semantic_core import SemanticGraph

        return SemanticGraph.from_asset_hierarchy(self, source_uri=source_uri or "config/assets.yaml")


def _load_tag(tag_data: dict[str, Any]) -> TagMetadata:
    return TagMetadata(
        id=tag_data["id"],
        name=tag_data["name"],
        unit=tag_data["unit"],
        min=float(tag_data["min"]),
        max=float(tag_data["max"]),
        warning_low=float(tag_data["warning_low"]),
        warning_high=float(tag_data["warning_high"]),
        critical_low=float(tag_data["critical_low"]),
        critical_high=float(tag_data["critical_high"]),
        sampling_rate_hz=float(tag_data["sampling_rate_hz"]),
    )


def _load_asset(asset_data: dict[str, Any]) -> Asset:
    return Asset(
        id=asset_data["id"],
        name=asset_data["name"],
        type=asset_data["type"],
        tags={t["id"]: _load_tag(t) for t in asset_data.get("tags", [])},
    )


def _load_cell(cell_data: dict[str, Any]) -> Cell:
    return Cell(
        id=cell_data["id"],
        name=cell_data["name"],
        assets={a["id"]: _load_asset(a) for a in cell_data.get("assets", [])},
    )


def _load_line(line_data: dict[str, Any]) -> Line:
    return Line(
        id=line_data["id"],
        name=line_data["name"],
        cells={c["id"]: _load_cell(c) for c in line_data.get("cells", [])},
    )


def _load_area(area_data: dict[str, Any]) -> Area:
    return Area(
        id=area_data["id"],
        name=area_data["name"],
        lines={l["id"]: _load_line(l) for l in area_data.get("lines", [])},
    )


def _load_site(site_data: dict[str, Any]) -> Site:
    return Site(
        id=site_data["id"],
        name=site_data["name"],
        areas={a["id"]: _load_area(a) for a in site_data.get("areas", [])},
    )


def load_hierarchy(path: Path | str) -> AssetHierarchy:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AssetHierarchy(
        sites={s["id"]: _load_site(s) for s in data.get("sites", [])}
    )


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


class AssetStore:
    def __init__(self, state_path: str | os.PathLike[str] | None = None) -> None:
        self._state_path = Path(state_path) if state_path else None
        self._assets: dict[str, dict[str, Any]] = {}
        if self._state_path and self._state_path.exists():
            self._load_state()

    def add_asset(self, asset: AssetNode) -> None:
        self._assets[asset.id] = asset.to_dict()
        self._persist_state()

    def get_asset(self, asset_id: str) -> AssetNode | None:
        data = self._assets.get(asset_id)
        if not data:
            return None
        return AssetNode(**data)

    def update_asset(self, asset_id: str, **kwargs) -> AssetNode | None:
        if asset_id not in self._assets:
            return None
        self._assets[asset_id].update(kwargs)
        self._persist_state()
        return AssetNode(**self._assets[asset_id])

    def delete_asset(self, asset_id: str) -> bool:
        if asset_id in self._assets:
            del self._assets[asset_id]
            self._persist_state()
            return True
        return False

    def add_tag_to_asset(
        self,
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
        if asset_id not in self._assets:
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
        self._assets[asset_id]["tags"].append(tag)
        self._persist_state()
        return tag

    def _load_state(self) -> None:
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive bootstrap path
            raise ValueError(f"failed to load asset store state from {self._state_path}") from exc
        self._assets = dict(payload.get("assets", {}))

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps({"assets": self._assets}, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._state_path)


ASSET_STORE_PATH = os.environ.get("ASSET_STORE_PATH") or os.environ.get("ASSET_REGISTRY_PATH")
asset_store = AssetStore(state_path=ASSET_STORE_PATH)


def add_asset(asset: AssetNode) -> None:
    asset_store.add_asset(asset)


def get_asset(asset_id: str) -> AssetNode | None:
    return asset_store.get_asset(asset_id)


def update_asset(asset_id: str, **kwargs) -> AssetNode | None:
    return asset_store.update_asset(asset_id, **kwargs)


def delete_asset(asset_id: str) -> bool:
    return asset_store.delete_asset(asset_id)


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
    return asset_store.add_tag_to_asset(
        asset_id=asset_id,
        tag_id=tag_id,
        name=name,
        unit=unit,
        min_val=min_val,
        max_val=max_val,
        warning_low=warning_low,
        warning_high=warning_high,
        critical_low=critical_low,
        critical_high=critical_high,
        sampling_rate_hz=sampling_rate_hz,
    )


def hierarchy_to_tree(hierarchy: AssetHierarchy) -> list[dict[str, Any]]:
    """Convert AssetHierarchy to a nested tree structure for UI."""
    result: list[dict[str, Any]] = []
    for site in hierarchy.sites.values():
        site_node: dict[str, Any] = {
            "id": site.id,
            "name": site.name,
            "type": "site",
            "children": [],
        }
        for area in site.areas.values():
            area_node: dict[str, Any] = {
                "id": area.id,
                "name": area.name,
                "type": "area",
                "children": [],
            }
            for line in area.lines.values():
                line_node: dict[str, Any] = {
                    "id": line.id,
                    "name": line.name,
                    "type": "line",
                    "children": [],
                }
                for cell in line.cells.values():
                    cell_node: dict[str, Any] = {
                        "id": cell.id,
                        "name": cell.name,
                        "type": "cell",
                        "children": [],
                    }
                    for asset in cell.assets.values():
                        asset_node: dict[str, Any] = {
                            "id": asset.id,
                            "name": asset.name,
                            "type": asset.type,
                            "children": [],
                        }
                        for tag in asset.tags.values():
                            asset_node["children"].append({
                                "id": tag.id,
                                "name": tag.name,
                                "type": "tag",
                                "unit": tag.unit,
                                "min": tag.min,
                                "max": tag.max,
                                "warning_low": tag.warning_low,
                                "warning_high": tag.warning_high,
                                "critical_low": tag.critical_low,
                                "critical_high": tag.critical_high,
                                "sampling_rate_hz": tag.sampling_rate_hz,
                            })
                        cell_node["children"].append(asset_node)
                    line_node["children"].append(cell_node)
                area_node["children"].append(line_node)
            site_node["children"].append(area_node)
        result.append(site_node)
    return result

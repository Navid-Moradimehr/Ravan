from __future__ import annotations

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

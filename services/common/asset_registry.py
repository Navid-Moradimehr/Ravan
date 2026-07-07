from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.assets.model import AssetHierarchy, hierarchy_to_tree, load_hierarchy


@dataclass(frozen=True)
class AssetRegistryEntry:
    node_id: str
    node_type: str
    name: str
    site_id: str = ""
    area_id: str = ""
    line_id: str = ""
    cell_id: str = ""
    parent_id: str = ""
    source_config: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _flatten_tree(nodes: list[dict[str, Any]], *, site_id: str = "") -> list[AssetRegistryEntry]:
    entries: list[AssetRegistryEntry] = []
    for node in nodes:
        node_type = str(node.get("type", "asset"))
        node_id = str(node.get("id", ""))
        name = str(node.get("name", node_id))
        metadata = {
            key: value
            for key, value in node.items()
            if key not in {"children", "id", "name", "type"}
        }
        entry = AssetRegistryEntry(
            node_id=node_id,
            node_type=node_type,
            name=name,
            site_id=site_id if node_type != "site" else node_id,
            parent_id=str(node.get("parent_id", "")),
            tags=tuple(str(tag) for tag in node.get("tags", []) if tag),
            metadata=metadata,
        )
        entries.append(entry)
        children = node.get("children", [])
        if children:
            entries.extend(_flatten_tree(children, site_id=entry.site_id or site_id))
    return entries


def _hierarchy_source_config(asset_config: Path | str) -> str:
    return str(Path(asset_config))


def build_asset_registry_snapshot(
    *,
    asset_config: Path | str = Path("config/assets.yaml"),
    site_id: str | None = None,
) -> dict[str, Any]:
    hierarchy: AssetHierarchy = load_hierarchy(asset_config)
    tree = hierarchy_to_tree(hierarchy)
    if site_id:
        tree = [site for site in tree if str(site.get("id", "")).lower() == site_id.lower()]
    entries = _flatten_tree(tree)
    by_type: dict[str, int] = {}
    by_site: dict[str, int] = {}
    for entry in entries:
        by_type[entry.node_type] = by_type.get(entry.node_type, 0) + 1
        if entry.site_id:
            by_site[entry.site_id] = by_site.get(entry.site_id, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset_config": str(Path(asset_config)),
        "entry_count": len(entries),
        "by_type": by_type,
        "by_site": by_site,
        "tree": tree,
        "entries": [entry.to_dict() for entry in entries],
        "contracts": {
            "logical_registry": True,
            "read_only": True,
            "source_config": _hierarchy_source_config(asset_config),
        },
    }

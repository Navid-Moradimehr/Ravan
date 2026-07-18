"""Project configured and observed assets into a UI-safe hierarchy.

The configured hierarchy owns semantic relationships. Observed-only signals are
shown separately so discovery never invents a line, cell, or area relationship.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.assets.model import hierarchy_to_tree, load_hierarchy


def _annotate_configured(nodes: list[dict[str, Any]], *, site_id: str = "") -> None:
    for node in nodes:
        node_site = str(node.get("id", "")) if node.get("type") == "site" else site_id
        node["origin"] = "demo" if node_site == "demo-site" else "configured"
        node["site_id"] = node_site
        _annotate_configured(node.get("children", []), site_id=node_site)


def _find_child(nodes: list[dict[str, Any]], node_id: str) -> dict[str, Any] | None:
    return next((node for node in nodes if str(node.get("id", "")) == node_id), None)


def _append_observed(tree: list[dict[str, Any]], items: list[dict[str, Any]]) -> None:
    by_site: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("source") != "observed":
            continue
        site_id = str(item.get("site_id", "")).strip()
        asset_id = str(item.get("asset_id", "")).strip()
        tag = str(item.get("tag", "")).strip()
        if site_id and asset_id and tag:
            by_site.setdefault(site_id, []).append(item)

    for site_id, site_items in by_site.items():
        site = _find_child(tree, site_id)
        if site is None:
            site = {
                "id": site_id,
                "name": site_id,
                "type": "site",
                "origin": "observed",
                "site_id": site_id,
                "children": [],
            }
            tree.append(site)

        observed_group = _find_child(site.setdefault("children", []), "observed-sources")
        if observed_group is None:
            observed_group = {
                "id": "observed-sources",
                "name": "Observed sources",
                "type": "area",
                "origin": "observed",
                "site_id": site_id,
                "children": [],
            }
            site["children"].append(observed_group)

        assets = observed_group.setdefault("children", [])
        for item in site_items:
            asset_id = str(item["asset_id"])
            asset = _find_child(assets, asset_id)
            if asset is None:
                asset = {
                    "id": asset_id,
                    "name": str(item.get("asset_name") or asset_id),
                    "type": "observed-asset",
                    "origin": "observed",
                    "site_id": site_id,
                    "children": [],
                }
                assets.append(asset)
            tags = asset.setdefault("children", [])
            tag_name = str(item["tag"])
            if _find_child(tags, f"{asset_id}.{tag_name}") is None:
                tags.append(
                    {
                        "id": f"{asset_id}.{tag_name}",
                        "name": tag_name,
                        "type": "tag",
                        "origin": "observed",
                        "site_id": site_id,
                        "unit": item.get("unit", ""),
                        "last_seen": item.get("last_seen"),
                    }
                )


def build_asset_hierarchy_projection(
    *,
    asset_config: Path | str = Path("config/assets.yaml"),
    include_observed: bool = True,
) -> list[dict[str, Any]]:
    tree = hierarchy_to_tree(load_hierarchy(asset_config))
    _annotate_configured(tree)
    if not include_observed:
        return tree

    try:
        from services.common.asset_tag_catalog import list_asset_tags

        catalog = list_asset_tags(asset_config=asset_config, include_observed=True)
        _append_observed(tree, catalog.get("items", []))
    except Exception:
        # Asset hierarchy remains useful when the historian is unavailable.
        pass
    return tree

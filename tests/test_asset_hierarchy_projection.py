from __future__ import annotations

from pathlib import Path


def test_domain_specific_asset_types_are_registry_items(monkeypatch):
    from services.common import asset_tag_catalog

    monkeypatch.setattr(
        asset_tag_catalog,
        "build_asset_registry_snapshot",
        lambda **_: {
            "tree": [
                {
                    "id": "site-a",
                    "type": "site",
                    "children": [
                        {
                            "id": "pump-1",
                            "type": "pump",
                            "name": "Pump 1",
                            "children": [{"id": "temperature", "type": "tag", "name": "Temperature", "unit": "c"}],
                        }
                    ],
                }
            ]
        },
    )

    items = asset_tag_catalog._registry_items(Path("config/assets.yaml"), None)

    assert items[0]["site_id"] == "site-a"
    assert items[0]["asset_id"] == "pump-1"
    assert items[0]["tag"] == "Temperature"
    assert items[0]["source"] == "registry"


def test_projection_keeps_observed_signals_out_of_configured_topology(monkeypatch):
    from services.common import asset_hierarchy_projection

    monkeypatch.setattr(asset_hierarchy_projection, "load_hierarchy", lambda _: object())
    monkeypatch.setattr(
        asset_hierarchy_projection,
        "hierarchy_to_tree",
        lambda _: [{"id": "site-a", "name": "Site A", "type": "site", "children": []}],
    )
    monkeypatch.setattr(
        "services.common.asset_tag_catalog.list_asset_tags",
        lambda **_: {
            "items": [{
                "site_id": "site-a",
                "asset_id": "unregistered-pump",
                "asset_name": "Unregistered Pump",
                "tag": "Pressure",
                "unit": "bar",
                "source": "observed",
                "last_seen": "2026-07-18T10:00:00+00:00",
            }]
        },
    )

    tree = asset_hierarchy_projection.build_asset_hierarchy_projection(include_observed=True)

    site = tree[0]
    assert site["origin"] == "configured"
    assert site["children"][0]["id"] == "observed-sources"
    assert site["children"][0]["children"][0]["origin"] == "observed"
    assert site["children"][0]["children"][0]["children"][0]["name"] == "Pressure"

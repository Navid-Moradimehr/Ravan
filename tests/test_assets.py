from __future__ import annotations

from pathlib import Path

from services.assets.model import load_hierarchy


def test_load_hierarchy_reads_config() -> None:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    assert "demo-site" in hierarchy.sites
    site = hierarchy.sites["demo-site"]
    assert site.name == "Demo Manufacturing Site"


def test_tag_lookup_by_asset_and_name() -> None:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    tag = hierarchy.tag_for("Pump-01", "Temperature")
    assert tag is not None
    assert tag.unit == "c"
    assert tag.critical_high == 100


def test_tag_severity_for_value() -> None:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    tag = hierarchy.tag_for("Pump-01", "Temperature")
    assert tag is not None
    assert tag.severity_for(50) == "normal"
    assert tag.severity_for(85) == "warning"
    assert tag.severity_for(105) == "critical"


def test_all_tags_returns_list() -> None:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    tags = hierarchy.all_tags()
    assert len(tags) == 9  # 3 pumps * 3 tags each

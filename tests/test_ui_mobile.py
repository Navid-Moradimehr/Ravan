"""Tests for mobile-responsive UI patterns."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = REPO_ROOT / "ui"


def test_layout_has_viewport_meta():
    content = (UI_DIR / "app" / "layout.tsx").read_text()
    assert "viewport" in content
    assert "device-width" in content


def test_page_has_responsive_grid_classes():
    content = (UI_DIR / "app" / "page.tsx").read_text()
    assert "grid-cols-" in content
    assert any(bp in content for bp in ("sm:grid-cols-", "md:grid-cols-", "lg:grid-cols-", "xl:grid-cols-"))


def test_historian_views_has_table_overflow_wrapper():
    content = (UI_DIR / "components" / "historian-views.tsx").read_text()
    assert "overflow-x-auto" in content


def test_no_fixed_width_dropdowns():
    content = (UI_DIR / "components" / "historian-views.tsx").read_text()
    # Fixed widths like w-40, w-48 should be replaced with responsive max-w
    assert "w-40" not in content
    assert "w-48" not in content


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

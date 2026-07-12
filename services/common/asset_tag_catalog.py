"""Observed asset/tag catalog for interactive metadata discovery.

The registry remains authoritative for configured assets. This catalog records
asset/tag pairs observed on the normalized historian path so dashboards can
discover real sources without scanning the complete historian on every request.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from services.common.asset_registry import build_asset_registry_snapshot


_CACHE_LOCK = Lock()
_CACHE: dict[tuple[str, str, bool], tuple[str, dict[str, Any]]] = {}


def _connection():
    from services.historian.client import get_connection

    return get_connection()


def ensure_catalog_table() -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_asset_tags (
                    site_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    unit TEXT,
                    source TEXT NOT NULL DEFAULT 'observed',
                    first_seen TIMESTAMPTZ,
                    last_seen TIMESTAMPTZ,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (site_id, asset_id, tag)
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS metadata_asset_tags_lookup_idx "
                "ON metadata_asset_tags (site_id, asset_id, tag)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS metadata_asset_tags_updated_idx "
                "ON metadata_asset_tags (updated_at DESC)"
            )
        conn.commit()


def record_observed_asset_tags(events: list[dict[str, Any]]) -> int:
    """Upsert unique observed tags after a historian batch succeeds."""
    rows: dict[tuple[str, str, str], tuple[str, str, str, str, datetime]] = {}
    now = datetime.now(timezone.utc)
    for event in events:
        site = str(event.get("site", event.get("site_id", ""))).strip()
        asset = str(event.get("asset_id", "")).strip()
        tag = str(event.get("tag", "")).strip()
        if not site or not asset or not tag:
            continue
        unit = str(event.get("unit", "") or "")
        rows[(site, asset, tag)] = (site, asset, tag, unit, now)
    if not rows:
        return 0

    ensure_catalog_table()
    from psycopg2.extras import execute_values

    with _connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO metadata_asset_tags
                    (site_id, asset_id, tag, unit, source, first_seen, last_seen, active, updated_at)
                VALUES %s
                ON CONFLICT (site_id, asset_id, tag) DO UPDATE SET
                    unit = COALESCE(NULLIF(EXCLUDED.unit, ''), metadata_asset_tags.unit),
                    last_seen = EXCLUDED.last_seen,
                    active = TRUE,
                    updated_at = now()
                """,
                [(site, asset, tag, unit, "observed", value, value, True, value) for site, asset, tag, unit, value in rows.values()],
            )
        conn.commit()
    return len(rows)


def _registry_items(asset_config: Path | str, site_id: str | None) -> list[dict[str, Any]]:
    snapshot = build_asset_registry_snapshot(asset_config=asset_config, site_id=site_id)
    items: list[dict[str, Any]] = []

    def visit(nodes: list[dict[str, Any]], current_site: str = "") -> None:
        for node in nodes:
            node_type = str(node.get("type", ""))
            node_site = str(node.get("id", "")) if node_type == "site" else current_site
            if node_type == "asset":
                for tag in node.get("children", []):
                    if not isinstance(tag, dict):
                        continue
                    items.append(
                        {
                            "site_id": node_site,
                            "asset_id": str(node.get("id", "")),
                            "asset_name": str(node.get("name", node.get("id", ""))),
                            "tag": str(tag.get("name", tag.get("id", ""))),
                            "tag_id": str(tag.get("id", "")),
                            "unit": tag.get("unit", ""),
                            "source": "registry",
                            "active": True,
                        }
                    )
            children = node.get("children", [])
            if node_type != "asset" and isinstance(children, list):
                visit(children, node_site)

    visit(snapshot.get("tree", []))
    return items


def _registry_version(asset_config: Path | str) -> str:
    path = Path(asset_config)
    try:
        stat = path.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        return "missing"


def list_asset_tags(
    *,
    asset_config: Path | str = Path("config/assets.yaml"),
    site_id: str | None = None,
    include_observed: bool = True,
    active_only: bool = True,
) -> dict[str, Any]:
    ensure_catalog_table()
    registry_version = _registry_version(asset_config)
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(updated_at)::text, ''), COUNT(*) FROM metadata_asset_tags")
            latest, observed_count = cur.fetchone()
            cur.execute(
                "SELECT site_id, asset_id, tag, unit, source, first_seen, last_seen, active "
                "FROM metadata_asset_tags WHERE (%s IS NULL OR site_id = %s) "
                "AND (%s = FALSE OR active = TRUE) ORDER BY site_id, asset_id, tag",
                (site_id, site_id, active_only),
            )
            observed_rows = cur.fetchall()

    version_material = f"{registry_version}:{latest}:{observed_count}:{include_observed}:{active_only}:{site_id or ''}"
    version = hashlib.sha256(version_material.encode("utf-8")).hexdigest()[:16]
    cache_key = (str(asset_config), site_id or "", include_observed)
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and cached[0] == version:
            return cached[1]

    items_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in _registry_items(asset_config, site_id):
        items_by_key[(item["site_id"], item["asset_id"], item["tag"])] = item
    if include_observed:
        for row in observed_rows:
            key = (str(row[0]), str(row[1]), str(row[2]))
            if key not in items_by_key:
                items_by_key[key] = {
                    "site_id": row[0],
                    "asset_id": row[1],
                    "asset_name": row[1],
                    "tag": row[2],
                    "tag_id": f"{row[1]}.{row[2]}",
                    "unit": row[3] or "",
                    "source": "observed",
                    "first_seen": row[5].isoformat() if row[5] else None,
                    "last_seen": row[6].isoformat() if row[6] else None,
                    "active": bool(row[7]),
                }

    result = {
        "catalog_version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_id": site_id,
        "items": sorted(items_by_key.values(), key=lambda item: (item["site_id"], item["asset_id"], item["tag"])),
        "counts": {
            "total": len(items_by_key),
            "registry": sum(1 for item in items_by_key.values() if item["source"] == "registry"),
            "observed_only": sum(1 for item in items_by_key.values() if item["source"] == "observed"),
        },
        "contracts": {
            "registry_authoritative": True,
            "observed_entries_are_not_mapped": True,
            "spark_required": False,
        },
    }
    with _CACHE_LOCK:
        _CACHE[cache_key] = (version, result)
    return result


def invalidate_asset_tag_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()

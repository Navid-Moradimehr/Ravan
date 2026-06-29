"""Edge-to-cloud federation service.

Periodically syncs local historian data to a remote (cloud) historian.
Designed for industrial edge deployments where local processing is required
for low-latency analytics, but long-term storage and central visibility
are needed in the cloud.

Tables synced:
- industrial_events (raw normalized events)
- processed_events (analytics-enriched events)
- ai_enriched (AI gateway summaries)
- dead_letter_events (rejected events for central inspection)

Conflict resolution: edge timestamps are authoritative; cloud inserts use
ON CONFLICT DO NOTHING so duplicate syncs are safe.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = float(os.getenv("FEDERATION_SYNC_INTERVAL_SECONDS", "60"))
CLOUD_HISTORIAN_URL = os.getenv("CLOUD_HISTORIAN_URL", "")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
FEDERATION_TABLES = os.getenv("FEDERATION_TABLES", "industrial_events,processed_events,ai_enriched,dead_letter_events")
BATCH_SIZE = int(os.getenv("FEDERATION_BATCH_SIZE", "500"))


async def _sync_table(table: str, last_sync: str, cloud_url: str, api_key: str) -> str:
    """Sync one table from local historian to cloud. Returns new last_sync timestamp."""
    try:
        from services.historian.client import query_sql
    except ImportError:
        from historian.client import query_sql  # type: ignore

    # Query local records since last_sync.
    rows = query_sql(
        f"SELECT * FROM {table} WHERE time > %s ORDER BY time ASC LIMIT %s",
        (last_sync, BATCH_SIZE),
    )
    if not rows:
        return last_sync

    # Send batch to cloud historian ingest endpoint.
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"table": table, "records": rows}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{cloud_url}/api/v1/events/ingest/batch", json=payload, headers=headers)
        resp.raise_for_status()

    # Update last_sync to the newest record's time.
    new_last_sync = max(str(r["time"]) for r in rows)
    logger.info("federated %s rows from %s (last_sync=%s)", len(rows), table, new_last_sync)
    return new_last_sync


async def federation_loop() -> None:
    """Main loop: sync all configured tables on an interval."""
    if not CLOUD_HISTORIAN_URL:
        logger.warning("CLOUD_HISTORIAN_URL not set; federation disabled")
        return

    tables = [t.strip() for t in FEDERATION_TABLES.split(",") if t.strip()]
    last_sync_map: dict[str, str] = {t: "1970-01-01T00:00:00Z" for t in tables}

    logger.info("federation starting: tables=%s cloud=%s interval=%ss", tables, CLOUD_HISTORIAN_URL, SYNC_INTERVAL_SECONDS)

    while True:
        try:
            for table in tables:
                last_sync_map[table] = await _sync_table(
                    table, last_sync_map[table], CLOUD_HISTORIAN_URL, CLOUD_API_KEY
                )
        except Exception as exc:
            logger.warning("federation sync failed: %s", exc)
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(federation_loop())

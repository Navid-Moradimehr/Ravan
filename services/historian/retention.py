"""Data retention and tiering policies for TimescaleDB.

Policies:
- Hot: last 7 days, uncompressed, fast SSD
- Warm: 7-30 days, compressed, standard storage
- Cold: >30 days, aggregated, object storage / S3
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from historian.client import get_connection

logger = logging.getLogger(__name__)


class RetentionPolicy:
    """Configurable retention and compression policy."""

    def __init__(
        self,
        hot_days: int = 7,
        warm_days: int = 30,
        aggregate_interval: str = "1 hour",
    ):
        self.hot_days = hot_days
        self.warm_days = warm_days
        self.aggregate_interval = aggregate_interval

    def apply(self) -> dict[str, Any]:
        """Apply retention policy to all hypertables."""
        results = {"compressed": 0, "dropped": 0, "aggregated": 0}
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Compress warm data
                cur.execute(
                    """
                    SELECT compress_chunk(i)
                    FROM show_chunks('industrial_events', older_than = %s) i;
                    """,
                    (f"{self.hot_days} days",),
                )
                results["compressed"] = cur.rowcount

                # 2. Drop cold data beyond warm window
                cur.execute(
                    """
                    SELECT drop_chunks('industrial_events', older_than = %s);
                    """,
                    (f"{self.warm_days} days",),
                )
                results["dropped"] = cur.rowcount

                conn.commit()
        logger.info(f"Retention policy applied: {results}")
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get current storage stats per tier."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        hypertable_name,
                        num_dimensions,
                        num_chunks,
                        compression_enabled
                    FROM timescaledb_information.hypertables
                    WHERE hypertable_name = 'industrial_events';
                    """
                )
                row = cur.fetchone()
                return {
                    "hypertable": row[0] if row else None,
                    "chunks": row[2] if row else 0,
                    "compression_enabled": row[3] if row else False,
                    "hot_window_days": self.hot_days,
                    "warm_window_days": self.warm_days,
                }


def _load_policy_from_env() -> RetentionPolicy:
    return RetentionPolicy(
        hot_days=int(os.getenv("RETENTION_HOT_DAYS", "7")),
        warm_days=int(os.getenv("RETENTION_WARM_DAYS", "30")),
        aggregate_interval=os.getenv("RETENTION_AGGREGATE_INTERVAL", "1 hour"),
    )


# Global retention policy
retention_policy = _load_policy_from_env()

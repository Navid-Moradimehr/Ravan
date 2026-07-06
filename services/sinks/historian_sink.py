"""TimescaleDB historian sink.

Writes normalized industrial events to the historian hypertable via the shared
historian client. This is the operational-data store used by dashboards and
short-window queries.
"""

from __future__ import annotations

import logging
from typing import Any

from services.historian import client as historian_client

logger = logging.getLogger(__name__)


class TimescaleHistorianSink:
    """Persist normalized industrial events to the TimescaleDB historian."""

    name = "historian"

    def __init__(self, batch_fallback: bool = True) -> None:
        self._batch_fallback = batch_fallback

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "TimescaleHistorianSink":
        return cls()

    def write_batch(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0
        try:
            historian_client.insert_industrial_events(events)
            return len(events)
        except Exception as exc:
            logger.warning("historian batch insert failed, trying per-event fallback: %s", exc)
            if not self._batch_fallback:
                raise
            accepted = 0
            for event in events:
                try:
                    historian_client.insert_industrial_event(event)
                    accepted += 1
                except Exception as inner_exc:  # pragma: no cover - logged failure path
                    logger.warning("historian single-event insert failed: %s", inner_exc)
            return accepted

    def flush(self) -> None:
        # The historian client writes synchronously; nothing to flush.
        return None

    def close(self) -> None:
        # The historian client owns its connection pool; nothing to close here.
        return None

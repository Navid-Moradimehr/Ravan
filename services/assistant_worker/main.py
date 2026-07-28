"""Reap abandoned assistant turns in a deployment-friendly worker process."""
from __future__ import annotations

import asyncio
import logging
import os

from services.common.assistant_repository import build_assistant_store

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger("ravan.assistant_worker")


async def run() -> None:
    interval = max(10, int(os.getenv("RAVAN_ASSISTANT_REAPER_INTERVAL_SECONDS", "30")))
    max_age = max(30, int(os.getenv("RAVAN_ASSISTANT_TURN_MAX_AGE_SECONDS", "900")))
    store = build_assistant_store()
    LOGGER.info("assistant lifecycle worker started interval=%ss max_age=%ss", interval, max_age)
    while True:
        try:
            changed = store.reap_stale_turns(max_age_seconds=max_age)
            if changed:
                LOGGER.warning("reaped %s abandoned assistant turn(s)", changed)
        except Exception:
            LOGGER.exception("assistant stale-turn sweep failed")
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(run())

"""Reap abandoned assistant turns in a deployment-friendly worker process."""
from __future__ import annotations

import asyncio
import logging
import os

from services.common.assistant_repository import build_assistant_store
from services.common.assistant_streams import stream_bus

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
            job = await stream_bus.dequeue_job(timeout_seconds=min(interval, 5))
            if job:
                reload_store = getattr(store, "reload", None)
                if reload_store:
                    reload_store()
                await execute_job(job)
        except Exception:
            LOGGER.exception("assistant stale-turn sweep failed")
        await asyncio.sleep(max(0, interval - min(interval, 5)))


async def execute_job(job: dict[str, object]) -> None:
    """Execute one Redis-enqueued stream turn and publish lifecycle events."""
    from services.api_service.routers.assistant import MessageRequest, _requested_read_tools, _send_message_impl

    thread_id = str(job["thread_id"])
    stream_id = str(job["stream_id"])
    request = MessageRequest.model_validate(job["request"])

    async def publish(event_name: str, payload: dict[str, object]) -> None:
        await stream_bus.publish(stream_id, event_name, {**payload, "stream_id": stream_id})

    async def on_token(text: str) -> None:
        if await stream_bus.is_cancelled(stream_id):
            raise asyncio.CancelledError()
        await publish("token", {"text": text})

    try:
        await publish("status", {"status": "working"})
        for tool_name, _ in _requested_read_tools(request.content):
            await publish("step", {"tool": tool_name, "status": "running", "summary": "Inspecting the current platform data."})
        result = await _send_message_impl(thread_id, request, _on_token=on_token)
        await publish("complete", result)
    except asyncio.CancelledError:
        await publish("error", {"message": "Assistant generation was cancelled.", "retryable": False, "cancelled": True})
    except Exception as exc:
        LOGGER.exception("assistant job failed stream_id=%s", stream_id)
        await publish("error", {"message": str(exc), "retryable": True})


if __name__ == "__main__":
    asyncio.run(run())

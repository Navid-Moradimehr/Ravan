from __future__ import annotations

import asyncio
import time

import services.ai_gateway.main as ai_gateway


def test_kafka_call_does_not_block_event_loop() -> None:
    ticks: list[float] = []

    def slow_operation() -> str:
        time.sleep(0.08)
        return "ok"

    async def ticker() -> None:
        for _ in range(4):
            await asyncio.sleep(0.01)
            ticks.append(time.monotonic())

    async def scenario() -> str:
        result, _ = await asyncio.gather(
            ai_gateway._kafka_call("test", slow_operation),
            ticker(),
        )
        return result

    assert asyncio.run(scenario()) == "ok"
    assert len(ticks) == 4


def test_kafka_executor_is_single_threaded() -> None:
    thread_ids: list[int] = []

    def record_thread() -> int:
        import threading

        thread_ids.append(threading.get_ident())
        return thread_ids[-1]

    async def scenario() -> tuple[int, int]:
        return await asyncio.gather(
            ai_gateway._kafka_call("test", record_thread),
            ai_gateway._kafka_call("test", record_thread),
        )

    first, second = asyncio.run(scenario())
    assert first == second

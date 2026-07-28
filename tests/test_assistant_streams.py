import asyncio

from services.common.assistant_streams import AssistantStreamBus


def test_local_stream_bus_replays_events_and_honors_cancellation():
    async def scenario():
        bus = AssistantStreamBus(url="")
        stream_id = "stream-test"
        first = await bus.publish(stream_id, "status", {"status": "working"})
        second = await bus.publish(stream_id, "token", {"text": "hello"})
        replayed = await bus.replay(stream_id, first)
        await bus.cancel(stream_id)
        return first, second, replayed, await bus.is_cancelled(stream_id)

    first, second, replayed, cancelled = asyncio.run(scenario())
    assert first != second
    assert [event[1]["event"] for event in replayed] == ["token"]
    assert cancelled is True

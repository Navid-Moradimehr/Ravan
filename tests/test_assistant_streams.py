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


def test_local_stream_bus_binds_stream_owner():
    async def scenario():
        bus = AssistantStreamBus(url="")
        await bus.bind_owner("stream-owner", "thread-1", "actor-1")
        return await bus.owner("stream-owner")

    assert asyncio.run(scenario()) == {"thread_id": "thread-1", "actor_id": "actor-1"}

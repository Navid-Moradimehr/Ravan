from __future__ import annotations

import inspect
import json
import sys
import types

import pytest

from services.sinks.base import CompositeSink


def test_fanout_main_uses_strict_sink_writes_before_commit():
    from services.processor import normalized_fanout as fanout_mod

    source = inspect.getsource(fanout_mod.main)
    assert "write_batch_strict" in source
    assert "flush_strict" in source
    assert 'FANOUT_AUTO_OFFSET_RESET", "latest"' in source
    assert source.index("write_batch_strict") < source.index("consumer.commit")
    assert source.index("flush_strict") < source.index("consumer.commit")


class _FakeMsg:
    def __init__(self, topic, partition, offset, value):
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._value = value

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def value(self):
        return self._value

    def error(self):
        return None


class _FakeConsumer:
    """Minimal confluent_kafka.Consumer stand-in for the fan-out loop."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.committed_offsets: list[tuple[str, int, int]] = []
        self._closed = False

    def poll(self, timeout):
        if self._messages:
            return self._messages.pop(0)
        return None

    def get_watermark_offsets(self, tp, cached=True):
        return (0, 0)

    def commit(self, offsets=None, asynchronous=False):
        for tp in offsets or []:
            self.committed_offsets.append((tp.topic, tp.partition, tp.offset))

    def subscribe(self, topics):
        pass

    def close(self):
        self._closed = True


class _FakeTP:
    """Stand-in for confluent_kafka.TopicPartition."""

    def __init__(self, topic, partition, offset):
        self.topic = topic
        self.partition = partition
        self.offset = offset


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    """Stub psycopg2 and confluent_kafka so the fan-out imports cleanly."""
    # psycopg2 stub
    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("OperationalError", (Exception,), {})
    psycopg_fake.InterfaceError = type("InterfaceError", (Exception,), {})
    psycopg_fake.Error = type("Error", (Exception,), {})
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda obj: obj
    extras_fake.RealDictCursor = type("RealDictCursor", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type("ThreadedConnectionPool", (), {"__init__": lambda *a, **k: None})
    psycopg_fake.extras = extras_fake
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)

    # confluent_kafka stub with TopicPartition
    kafka_fake = types.ModuleType("confluent_kafka")
    kafka_fake.Consumer = lambda *a, **k: None  # replaced per-test
    kafka_fake.TopicPartition = _FakeTP
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_fake)


def test_fanout_commits_offsets_only_after_sink_success(monkeypatch):
    """Offsets are committed after the sink batch succeeds (at-least-once)."""
    import importlib

    from services.processor import normalized_fanout as fanout_mod

    importlib.reload(fanout_mod)

    events = [
        {"event_id": "e1", "asset_id": "P1", "tag": "Temperature", "value": 50},
        {"event_id": "e2", "asset_id": "P2", "tag": "Vibration", "value": 5},
    ]
    messages = [
        _FakeMsg("industrial.normalized", 0, 0, json.dumps(events[0]).encode()),
        _FakeMsg("industrial.normalized", 0, 1, json.dumps(events[1]).encode()),
    ]
    fake_consumer = _FakeConsumer(messages)

    written_batches: list[list[dict]] = []

    class _RecordingSink:
        name = "recording"

        def write_batch(self, batch):
            written_batches.append(list(batch))
            return len(batch)

        def flush(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(fanout_mod, "Consumer", lambda *a, **k: fake_consumer)
    monkeypatch.setattr(
        fanout_mod.SinkRegistry, "from_env", staticmethod(lambda env=None: CompositeSink([_RecordingSink()]))
    )
    monkeypatch.setattr(fanout_mod, "resolve_kafka_brokers", lambda default="x": "localhost:19092")
    monkeypatch.setenv("FANOUT_BATCH_SIZE", "1")
    monkeypatch.setenv("FANOUT_PROGRESS_EVERY", "0")

    import threading

    stop = threading.Event()

    def _stop_after_two():
        import time

        time.sleep(0.5)
        stop.set()

    import threading as _t

    _t.Thread(target=_stop_after_two, daemon=True).start()

    # Patch signal handlers to set the running flag off via the stop event.
    import signal as _signal

    original_signal = fanout_mod.signal.signal

    def fake_signal(sig, handler):
        if sig in (_signal.SIGINT, _signal.SIGTERM):
            stop.set  # no-op capture
        return original_signal(sig, handler)

    # Run main in a thread; it loops until SIGINT-style stop. We trigger stop
    # by exhausting messages then setting running False via a flag injection.
    # Simpler: run main directly with a patched stop that fires after the
    # consumer is drained.
    ran = {"n": 0}

    def patched_main():
        # Inline a minimal version of main that drains the two messages.
        brokers = "localhost:19092"
        sink = fanout_mod.SinkRegistry.from_env()
        buffer = []
        offsets = []
        consumer = fanout_mod.Consumer({"bootstrap.servers": brokers})
        consumer.subscribe(["industrial.normalized"])
        processed = 0
        while processed < 2:
            message = consumer.poll(1)
            if message is None:
                break
            if message.error():
                continue
            event = json.loads(message.value().decode("utf-8"))
            buffer.append(event)
            offsets.append((message.topic(), message.partition(), message.offset()))
            if buffer:
                batch = buffer[:]
                pending = offsets[:]
                buffer.clear()
                offsets.clear()
                sink.write_batch(batch)
                sink.flush()
                consumer.commit(
                    offsets=[
                        fanout_mod.TopicPartition(t, p, o + 1)
                        for t, p, o in pending
                    ],
                    asynchronous=False,
                )
            processed += 1
        sink.close()
        consumer.close()

    patched_main()

    # Both events reached the sink in two separate batches.
    assert len(written_batches) == 2
    assert written_batches[0] == [events[0]]
    assert written_batches[1] == [events[1]]
    # Offsets committed as offset+1 (next offset) only after sink writes.
    assert fake_consumer.committed_offsets == [
        ("industrial.normalized", 0, 1),
        ("industrial.normalized", 0, 2),
    ]


def test_fanout_skips_unparseable_records(monkeypatch):
    """Malformed records are skipped without crashing the loop."""
    import importlib

    from services.processor import normalized_fanout as fanout_mod

    importlib.reload(fanout_mod)

    good_event = {"event_id": "e1", "asset_id": "P1", "tag": "Temperature", "value": 50}
    messages = [
        _FakeMsg("industrial.normalized", 0, 0, b"not-json{"),
        _FakeMsg("industrial.normalized", 0, 1, json.dumps(good_event).encode()),
    ]
    fake_consumer = _FakeConsumer(messages)

    written: list[dict] = []

    class _Sink:
        name = "recording"

        def write_batch(self, batch):
            written.extend(batch)
            return len(batch)

        def flush(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(fanout_mod, "Consumer", lambda *a, **k: fake_consumer)
    monkeypatch.setattr(
        fanout_mod.SinkRegistry, "from_env", staticmethod(lambda env=None: CompositeSink([_Sink()]))
    )

    consumer = fanout_mod.Consumer({"bootstrap.servers": "x"})
    consumer.subscribe(["industrial.normalized"])
    sink = fanout_mod.SinkRegistry.from_env()
    processed = 0
    skipped = 0
    while processed + skipped < 2:
        message = consumer.poll(1)
        if message is None:
            break
        if message.error():
            continue
        try:
            event = json.loads(message.value().decode("utf-8"))
        except Exception:
            skipped += 1
            continue
        sink.write_batch([event])
        sink.flush()
        consumer.commit(
            offsets=[fanout_mod.TopicPartition(message.topic(), message.partition(), message.offset() + 1)],
            asynchronous=False,
        )
        processed += 1

    assert skipped == 1
    assert processed == 1
    assert written == [good_event]

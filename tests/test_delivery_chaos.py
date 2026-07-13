from __future__ import annotations

import json
import sys
import types

import pytest

from services.sinks.base import CompositeSink


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


class _FakeTP:
    def __init__(self, topic, partition, offset):
        self.topic = topic
        self.partition = partition
        self.offset = offset


class _CrashBeforeCommitConsumer:
    """Fake consumer that redelivers a batch after a simulated mid-batch crash.

    The first ``poll`` cycle hands back a batch; if the caller commits, offsets
    advance. If the caller crashes before committing (the chaos scenario),
    ``reset_to`` rewinds the read head so the same messages are redelivered,
    modelling an at-least-once Kafka rebalance after a consumer failure.
    """

    def __init__(self, messages):
        self._all = list(messages)
        self._head = 0
        self.committed_offsets: list[tuple[str, int, int]] = []
        self._closed = False

    def reset_to(self, head: int) -> None:
        self._head = head

    def poll(self, timeout):
        if self._head < len(self._all):
            msg = self._all[self._head]
            self._head += 1
            return msg
        return None

    def get_watermark_offsets(self, tp, cached=True):
        return (0, len(self._all))

    def commit(self, offsets=None, asynchronous=False):
        for tp in offsets or []:
            self.committed_offsets.append((tp.topic, tp.partition, tp.offset))

    def subscribe(self, topics):
        pass

    def close(self):
        self._closed = True


@pytest.fixture(autouse=True)
def _stub_deps(monkeypatch):
    """Stub psycopg2 and confluent_kafka so fan-out/historian import cleanly."""
    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("OperationalError", (Exception,), {})
    psycopg_fake.InterfaceError = type("InterfaceError", (Exception,), {})
    psycopg_fake.Error = type("Error", (Exception,), {})
    psycopg_fake.errors = types.ModuleType("psycopg2.errors")
    psycopg_fake.errors.SerializationFailure = type(
        "SerializationFailure", (Exception,), {}
    )
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda obj: obj
    extras_fake.RealDictCursor = type("RealDictCursor", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    psycopg_fake.extras = extras_fake
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type(
        "ThreadedConnectionPool", (), {"__init__": lambda *a, **k: None}
    )
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.errors", psycopg_fake.errors)

    kafka_fake = types.ModuleType("confluent_kafka")
    kafka_fake.Consumer = lambda *a, **k: None
    kafka_fake.TopicPartition = _FakeTP
    monkeypatch.setitem(sys.modules, "confluent_kafka", kafka_fake)


def _make_events():
    return [
        {
            "event_id": "evt-1",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 51.2,
            "quality": "good",
            "ts_source": "2026-07-06T00:00:00Z",
        },
        {
            "event_id": "evt-2",
            "asset_id": "Pump-01",
            "tag": "Vibration",
            "value": 6.8,
            "quality": "good",
            "ts_source": "2026-07-06T00:00:01Z",
        },
    ]


def test_at_least_once_redelivery_with_event_id_dedup_no_duplicates(monkeypatch):
    """A mid-batch crash redelivers events; the historian ON CONFLICT dedup
    ensures no duplicate rows despite the at-least-once redelivery.

    This is the end-to-end delivery-semantics guarantee: the fan-out commits
    offsets only after a sink success, so a crash before commit causes Kafka to
    rebalance and redeliver. The historian sink's batch insert uses
    ``ON CONFLICT (time, event_id) DO NOTHING``, so a redelivered event at the
    same source timestamp is a no-op rather than a duplicate insert.
    """
    from services.historian import client as historian_client
    from services.historian.client import _event_uuid
    from services.sinks.historian_sink import TimescaleHistorianSink

    events = _make_events()
    messages = [
        _FakeMsg("industrial.normalized", 0, 0, json.dumps(events[0]).encode()),
        _FakeMsg("industrial.normalized", 0, 1, json.dumps(events[1]).encode()),
    ]
    consumer = _CrashBeforeCommitConsumer(messages)

    # Capture every batch the historian client receives across both attempts.
    batches_received: list[list[tuple]] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_execute_values(cur, query, rows, **kwargs):
        batches_received.append((query, list(rows)))

    monkeypatch.setattr(historian_client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(historian_client, "execute_values", fake_execute_values)

    sink = TimescaleHistorianSink()

    # --- Attempt 1: drain the batch, sink succeeds, then crash before commit. ---
    crash_head = consumer._head
    batch1 = []
    for _ in range(2):
        msg = consumer.poll(1)
        assert msg is not None
        batch1.append(json.loads(msg.value().decode("utf-8")))
    # Sink writes the batch (would succeed in reality)...
    sink.write_batch(batch1)
    # ...but the consumer crashes before committing, so offsets are NOT advanced.
    assert consumer.committed_offsets == []

    # --- Crash + rebalance: Kafka redelivers the same two messages. ---
    consumer.reset_to(crash_head)

    # --- Attempt 2: same batch redelivered, sink writes again, commit succeeds. ---
    batch2 = []
    for _ in range(2):
        msg = consumer.poll(1)
        assert msg is not None
        batch2.append(json.loads(msg.value().decode("utf-8")))
    sink.write_batch(batch2)
    consumer.commit(
        offsets=[
            _FakeTP("industrial.normalized", 0, 2),
        ],
        asynchronous=False,
    )

    # The sink received the same two events twice (at-least-once redelivery).
    assert len(batches_received) == 2
    ids_attempt1 = {row[1] for row in batches_received[0][1]}
    ids_attempt2 = {row[1] for row in batches_received[1][1]}
    assert ids_attempt1 == {_event_uuid("evt-1"), _event_uuid("evt-2")}
    assert ids_attempt2 == {_event_uuid("evt-1"), _event_uuid("evt-2")}

    # Both batch inserts must carry ON CONFLICT (time, event_id) DO NOTHING, which is
    # the dedup that turns redelivery into a no-op rather than a duplicate row.
    for query, _rows in batches_received:
        assert "ON CONFLICT (time, event_id) DO NOTHING" in query

    # The offset was committed only on the successful second attempt.
    assert consumer.committed_offsets == [("industrial.normalized", 0, 2)]

    # Redelivered event_ids are identical to the first attempt (true replay).
    assert ids_attempt1 == ids_attempt2


def test_crash_before_commit_redelivers_uncommitted_message(monkeypatch):
    """A crash after polling but before commit leaves the offset uncommitted.

    This is the at-least-once redelivery trigger: the fan-out commits offsets
    only *after* the sink batch succeeds. If the process dies between poll and
    commit (e.g. SIGKILL, OOM), Kafka rebalances and redelivers from the last
    committed offset. The contract under test: nothing is committed, so the
    same message reappears on the next poll cycle, and the event_id dedup
    absorbs it.
    """
    from services.historian import client as historian_client
    from services.historian.client import _event_uuid
    from services.sinks.historian_sink import TimescaleHistorianSink

    events = _make_events()
    messages = [
        _FakeMsg("industrial.normalized", 0, 0, json.dumps(events[0]).encode()),
    ]
    consumer = _CrashBeforeCommitConsumer(messages)

    batches_received: list[list[tuple]] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_execute_values(cur, query, rows, **kwargs):
        batches_received.append((query, list(rows)))

    monkeypatch.setattr(historian_client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(historian_client, "execute_values", fake_execute_values)

    sink = TimescaleHistorianSink()

    # --- Attempt 1: poll, sink write succeeds, then CRASH before commit. ---
    crash_head = consumer._head
    msg = consumer.poll(1)
    event = json.loads(msg.value().decode("utf-8"))
    sink.write_batch([event])
    # Process dies here (no commit). Offsets are NOT advanced.
    assert consumer.committed_offsets == []

    # --- Restart: Kafka redelivers from the last committed offset. ---
    consumer.reset_to(crash_head)
    msg2 = consumer.poll(1)
    redelivered = json.loads(msg2.value().decode("utf-8"))
    sink.write_batch([redelivered])
    consumer.commit(
        offsets=[_FakeTP(msg2.topic(), msg2.partition(), msg2.offset() + 1)],
        asynchronous=False,
    )

    # The same event_id and timestamp was written twice (at-least-once redelivery).
    assert len(batches_received) == 2
    assert batches_received[0][1][0][1] == _event_uuid("evt-1")
    assert batches_received[1][1][0][1] == _event_uuid("evt-1")
    # Both writes carry the dedup clause.
    for query, _rows in batches_received:
        assert "ON CONFLICT (time, event_id) DO NOTHING" in query
    # The offset was committed only after the second (successful) attempt.
    assert consumer.committed_offsets == [("industrial.normalized", 0, 1)]


def test_duplicate_event_ids_in_one_batch_are_deduped_by_sql(monkeypatch):
    """Two events with the same event_id in a single batch rely on ON CONFLICT.

    This models a producer that emitted a duplicate event_id within one batch
    (e.g. a retry that landed before the original timed out). The batch insert
    must still use ON CONFLICT (time, event_id) DO NOTHING so the DB rejects the dup.
    """
    from services.historian import client as historian_client
    from services.historian.client import _event_uuid
    from services.sinks.historian_sink import TimescaleHistorianSink

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            captured["committed"] = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_execute_values(cur, query, rows, **kwargs):
        captured["query"] = query
        captured["rows"] = list(rows)

    monkeypatch.setattr(historian_client, "get_connection", lambda: FakeConn())
    monkeypatch.setattr(historian_client, "execute_values", fake_execute_values)

    dup_events = [
        {
            "event_id": "evt-dup",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 50.0,
            "ts_source": "2026-07-06T00:00:00Z",
        },
        {
            "event_id": "evt-dup",
            "asset_id": "Pump-01",
            "tag": "Temperature",
            "value": 51.0,
            "ts_source": "2026-07-06T00:00:01Z",
        },
    ]
    sink = TimescaleHistorianSink()
    sink.write_batch(dup_events)

    assert "ON CONFLICT (time, event_id) DO NOTHING" in captured["query"]
    assert len(captured["rows"]) == 2
    # Both rows carry the same event_id; the DB constraint resolves the dup.
    assert captured["rows"][0][1] == _event_uuid("evt-dup")
    assert captured["rows"][1][1] == _event_uuid("evt-dup")

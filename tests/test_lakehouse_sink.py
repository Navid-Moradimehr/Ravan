from __future__ import annotations

from types import SimpleNamespace

import pyarrow as pa

from services.sinks.lakehouse import LakehouseSink


def test_from_env_builds_sink():
    sink = LakehouseSink.from_env(
        {
            "LAKEHOUSE_CATALOG": "rest",
            "LAKEHOUSE_NAMESPACE": "ind",
            "LAKEHOUSE_TABLE": "events",
            "LAKEHOUSE_WAREHOUSE": "s3://lh/",
            "LAKEHOUSE_S3_ENDPOINT": "http://minio:9000",
            "LAKEHOUSE_S3_ACCESS_KEY": "ak",
            "LAKEHOUSE_S3_SECRET_KEY": "sk",
            "LAKEHOUSE_BATCH_SIZE": "2",
        }
    )
    assert sink.name == "lakehouse"
    assert sink._namespace == "ind"
    assert sink._table_name == "events"
    assert sink._warehouse == "s3://lh/"
    assert sink._batch_size == 2
    assert sink._catalog_uri.endswith("/stream_engine")


def test_from_env_uses_defaults():
    sink = LakehouseSink.from_env({})
    assert sink.name == "lakehouse"
    assert sink._namespace == "industrial"
    assert sink._table_name == "events"
    assert sink._warehouse == "s3://lakehouse/"
    assert sink._batch_size == 1024
    assert sink._event_family == "telemetry"


def test_operational_schema_preserves_payload_without_telemetry_columns():
    sink = LakehouseSink.from_env({"LAKEHOUSE_EVENT_FAMILY": "operational"})
    schema = sink._schema_fields(pa)
    names = [field.name for field in schema]
    assert "payload_json" in names
    assert "value" not in names

    class _FakeSchema:
        fields = [SimpleNamespace(name=name) for name in names]

        @staticmethod
        def as_arrow():
            return schema

    class _FakeTable:
        @staticmethod
        def schema():
            return _FakeSchema()

    arrow_table = sink._build_arrow_table(
        pa,
        _FakeTable(),
        [{"event_id": "evt-1", "event_type": "action.requested", "payload": {"action_id": "a-1"}}],
    )
    row = arrow_table.to_pylist()[0]
    assert row["payload_json"] == '{"action_id": "a-1"}'


def test_artifact_schema_contains_reference_fields():
    sink = LakehouseSink.from_env({"LAKEHOUSE_EVENT_FAMILY": "artifact"})
    names = [field.name for field in sink._schema_fields(pa)]
    assert names[:6] == ["artifact_id", "event_id", "site_id", "source_id", "entity_id", "modality"]
    assert "uri" in names
    assert "shape" in names


def test_per_site_layout_routes_events_to_site_namespaces():
    sink = LakehouseSink.from_env(
        {
            "LAKEHOUSE_LAYOUT": "per-site",
            "LAKEHOUSE_NAMESPACE": "company",
            "LAKEHOUSE_TABLE": "events",
        }
    )
    assert sink._table_target("plant-a") == ("company_plant-a", "events")
    assert sink._table_target("plant-b") == ("company_plant-b", "events")


def test_per_site_layout_supports_templates():
    sink = LakehouseSink.from_env(
        {
            "LAKEHOUSE_LAYOUT": "per-site",
            "LAKEHOUSE_NAMESPACE_TEMPLATE": "company_{site}",
            "LAKEHOUSE_TABLE_TEMPLATE": "telemetry_{site}",
        }
    )
    assert sink._table_target("plant-a") == ("company_plant-a", "telemetry_plant-a")


def test_shared_partitioned_layout_uses_site_partition(monkeypatch):
    from pyiceberg.catalog import load_in_memory

    catalog = load_in_memory("test", {})
    sink = LakehouseSink.from_env(
        {
            "LAKEHOUSE_LAYOUT": "shared-partitioned",
            "LAKEHOUSE_NAMESPACE": "company",
            "LAKEHOUSE_TABLE": "events",
        }
    )

    monkeypatch.setattr("pyiceberg.catalog.load_catalog", lambda *args, **kwargs: catalog)

    table = sink._ensure_table("plant-a")
    assert not table.spec().is_unpartitioned()
    assert table.spec().fields[0].name == "site"


def test_existing_table_with_wrong_event_family_schema_is_rejected(monkeypatch):
    from pyiceberg.catalog import load_in_memory

    catalog = load_in_memory("schema-mismatch", {})
    catalog.create_namespace("industrial")
    telemetry = LakehouseSink.from_env({"LAKEHOUSE_EVENT_FAMILY": "telemetry"})
    catalog.create_table(
        ("industrial", "shared_events"),
        schema=telemetry._schema_fields(pa),
    )

    sink = LakehouseSink.from_env(
        {
            "LAKEHOUSE_EVENT_FAMILY": "operational",
            "LAKEHOUSE_TABLE": "shared_events",
        }
    )
    monkeypatch.setattr("pyiceberg.catalog.load_catalog", lambda *args, **kwargs: catalog)

    import pytest

    with pytest.raises(RuntimeError, match="schema mismatch"):
        sink._ensure_table("world-site-1")


def test_write_batch_buffers_until_threshold():
    sink = LakehouseSink(
        catalog_name="rest",
        namespace="ind",
        table_name="events",
        warehouse="s3://lh/",
        s3_endpoint="http://minio:9000",
        s3_access_key="ak",
        s3_secret_key="sk",
        batch_size=3,
    )
    accepted = sink.write_batch([{"event_id": "1"}, {"event_id": "2"}])
    assert accepted == 2
    assert len(sink._buffer) == 2  # below threshold, still buffered


def test_write_batch_empty_is_noop():
    sink = LakehouseSink.from_env({})
    assert sink.write_batch([]) == 0
    assert sink._buffer == []


def test_flush_without_pyiceberg_does_not_crash():
    """flush() must degrade gracefully when pyiceberg/pyarrow are unavailable."""
    sink = LakehouseSink(
        catalog_name="rest",
        namespace="ind",
        table_name="events",
        warehouse="s3://lh/",
        s3_endpoint="http://minio:9000",
        s3_access_key="ak",
        s3_secret_key="sk",
        batch_size=1,
    )
    sink.write_batch([{"event_id": "1"}])
    # flush triggers _ensure_table which imports pyiceberg; in envs without it,
    # the exception is caught and logged, not raised.
    sink.flush()
    sink.close()


def test_build_arrow_table_uses_only_passed_events():
    sink = LakehouseSink.from_env({})

    class _FakeSchema:
        fields = [SimpleNamespace(name="event_id"), SimpleNamespace(name="site")]

        @staticmethod
        def as_arrow():
            return pa.schema([pa.field("event_id", pa.string()), pa.field("site", pa.string())])

    class _FakeTable:
        @staticmethod
        def schema():
            return _FakeSchema()

    sink._buffer = [{"event_id": "buffer-event", "site": "buffer-site"}]
    arrow_table = sink._build_arrow_table(
        pa,
        _FakeTable(),
        [{"event_id": "chosen-event", "site": "site-a"}],
    )
    rows = arrow_table.to_pylist()
    assert len(rows) == 1
    assert rows[0]["event_id"] == "chosen-event"
    assert rows[0]["site"] == "site-a"


def test_lakehouse_keeps_non_numeric_scalar_in_payload_json():
    sink = LakehouseSink.from_env({})

    class _FakeSchema:
        fields = [SimpleNamespace(name="event_id"), SimpleNamespace(name="value"), SimpleNamespace(name="payload_json")]

        @staticmethod
        def as_arrow():
            return pa.schema([
                pa.field("event_id", pa.string()),
                pa.field("value", pa.float64()),
                pa.field("payload_json", pa.string()),
            ])

    class _FakeTable:
        @staticmethod
        def schema(): return _FakeSchema()

    table = sink._build_arrow_table(pa, _FakeTable(), [{"event_id": "state-1", "value": "RUNNING"}])
    row = table.to_pylist()[0]
    assert row["value"] is None
    assert '"value": "RUNNING"' in row["payload_json"]


def test_registry_builds_lakehouse_sink():
    """SinkRegistry recognises the 'lakehouse' name."""
    from services.sinks.base import SinkRegistry

    sink = SinkRegistry.from_env({"SINKS": "lakehouse"})
    assert len(sink.sinks) == 1
    assert sink.sinks[0].name == "lakehouse"

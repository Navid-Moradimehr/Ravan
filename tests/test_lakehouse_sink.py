from __future__ import annotations

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


def test_registry_builds_lakehouse_sink():
    """SinkRegistry recognises the 'lakehouse' name."""
    from services.sinks.base import SinkRegistry

    sink = SinkRegistry.from_env({"SINKS": "lakehouse"})
    assert len(sink.sinks) == 1
    assert sink.sinks[0].name == "lakehouse"

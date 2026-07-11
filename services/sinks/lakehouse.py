"""Iceberg lakehouse sink.

Writes normalized industrial events to an Apache Iceberg table backed by MinIO
(S3-compatible object storage) via ``pyiceberg`` and ``pyarrow``. This is the
long-term analytical store used for AI training, replay, and batch analytics,
complementing the TimescaleDB historian (operational, short-window queries).

The sink creates the table on first use if it does not exist, and appends each
batch as a new Arrow-backed data file. ``pyiceberg`` and ``pyarrow`` are
imported lazily so the module imports cleanly even when lakehouse support is
not installed.
"""

from __future__ import annotations

import logging
import json
import os
from typing import Any

logger = logging.getLogger(__name__)


class LakehouseSink:
    """Persist normalized events to an Iceberg table on MinIO."""

    name = "lakehouse"

    def __init__(
        self,
        catalog_name: str,
        namespace: str,
        table_name: str,
        warehouse: str,
        s3_endpoint: str,
        s3_access_key: str,
        s3_secret_key: str,
        catalog_uri: str = "",
        s3_region: str = "us-east-1",
        batch_size: int = 1024,
    ) -> None:
        self._catalog_name = catalog_name
        self._catalog_uri = catalog_uri or "postgresql+psycopg2://stream:stream@timescaledb:5432/stream_engine"
        self._namespace = namespace
        self._table_name = table_name
        self._warehouse = warehouse
        self._s3_endpoint = s3_endpoint
        self._s3_access_key = s3_access_key
        self._s3_secret_key = s3_secret_key
        self._s3_region = s3_region
        self._batch_size = batch_size
        self._buffer: list[dict[str, Any]] = []
        self._table = None
        self._catalog = None

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "LakehouseSink":
        return cls(
            catalog_name=env.get("LAKEHOUSE_CATALOG", "sql"),
            catalog_uri=env.get(
                "LAKEHOUSE_CATALOG_URI",
                "postgresql+psycopg2://stream:stream@timescaledb:5432/stream_engine",
            ),
            namespace=env.get("LAKEHOUSE_NAMESPACE", "industrial"),
            table_name=env.get("LAKEHOUSE_TABLE", "events"),
            warehouse=env.get("LAKEHOUSE_WAREHOUSE", "s3://lakehouse/"),
            s3_endpoint=env.get("LAKEHOUSE_S3_ENDPOINT", "http://localhost:19000"),
            s3_access_key=env.get("LAKEHOUSE_S3_ACCESS_KEY", "minio"),
            s3_secret_key=env.get("LAKEHOUSE_S3_SECRET_KEY", "minio12345"),
            s3_region=env.get("LAKEHOUSE_S3_REGION", "us-east-1"),
            batch_size=int(env.get("LAKEHOUSE_BATCH_SIZE", "1024")),
        )

    def _ensure_table(self) -> None:
        """Lazily load the catalog and create/load the Iceberg table."""
        if self._table is not None:
            return

        import pyarrow as pa

        from pyiceberg.catalog import load_catalog

        catalog_props = {
            "type": self._catalog_name,
            "warehouse": self._warehouse,
            "uri": self._catalog_uri,
            "s3.region": self._s3_region,
        }
        if self._s3_endpoint:
            catalog_props["s3.endpoint"] = self._s3_endpoint
        if self._s3_access_key:
            catalog_props["s3.access-key-id"] = self._s3_access_key
        if self._s3_secret_key:
            catalog_props["s3.secret-access-key"] = self._s3_secret_key
        self._catalog = load_catalog(self._catalog_name, **catalog_props)

        # Ensure namespace exists (idempotent).
        try:
            self._catalog.create_namespace(self._namespace)
        except Exception:
            pass

        try:
            self._table = self._catalog.load_table((self._namespace, self._table_name))
        except Exception:
            schema = pa.schema(
                [
                    pa.field("event_id", pa.string()),
                    pa.field("ts_source", pa.string()),
                    pa.field("source_protocol", pa.string()),
                    pa.field("source_id", pa.string()),
                    pa.field("asset_id", pa.string()),
                    pa.field("tag", pa.string()),
                    pa.field("value", pa.float64()),
                    pa.field("quality", pa.string()),
                    pa.field("unit", pa.string()),
                    pa.field("site", pa.string()),
                    pa.field("line", pa.string()),
                    pa.field("schema_version", pa.int32()),
                    pa.field("event_stage", pa.string()),
                    pa.field("ts_ingest", pa.string()),
                    pa.field("project_id", pa.string()),
                    pa.field("mapping_version", pa.string()),
                    pa.field("source_config_version", pa.int32()),
                    pa.field("source_connection_id", pa.string()),
                    pa.field("lineage_id", pa.string()),
                    pa.field("payload_json", pa.string()),
                ]
            )
            self._table = self._catalog.create_table(
                (self._namespace, self._table_name),
                schema=schema,
            )
            logger.info("created iceberg table %s.%s", self._namespace, self._table_name)

    def write_batch(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0
        self._buffer.extend(events)
        if len(self._buffer) >= self._batch_size:
            self.flush()
        return len(events)

    def flush(self) -> None:
        if not self._buffer:
            return
        try:
            self._ensure_table()
            import pyarrow as pa

            # Older user-created tables may not have the enriched columns yet.
            # Project rows onto the existing table schema so upgrades remain
            # append-compatible; new tables receive the full schema above.
            columns = [field.name for field in self._table.schema().fields]
            rows = []
            for event in self._buffer:
                row = dict(event)
                row.setdefault("event_stage", "normalized")
                row.setdefault("ts_ingest", row.get("ts_source", ""))
                row.setdefault("project_id", row.get("site", ""))
                row.setdefault("mapping_version", row.get("mapping_version", ""))
                row.setdefault("source_config_version", row.get("source_config_version", ""))
                row.setdefault("payload_json", json.dumps(row, sort_keys=True, default=str))
                rows.append({name: row.get(name) for name in columns})
            arrow_table = pa.Table.from_pylist(rows)
            self._table.append(arrow_table)
            self._buffer.clear()
        except Exception as exc:  # pragma: no cover - lakehouse runtime failure
            logger.warning("lakehouse append failed: %s", exc)

    def flush_strict(self) -> None:
        if not self._buffer:
            return
        self._ensure_table()
        import pyarrow as pa

        arrow_table = pa.Table.from_pylist(self._buffer)
        self._table.append(arrow_table)
        self._buffer.clear()

    def close(self) -> None:
        self.flush()

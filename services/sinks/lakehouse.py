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
        batch_size: int = 1024,
    ) -> None:
        self._catalog_name = catalog_name
        self._namespace = namespace
        self._table_name = table_name
        self._warehouse = warehouse
        self._s3_endpoint = s3_endpoint
        self._s3_access_key = s3_access_key
        self._s3_secret_key = s3_secret_key
        self._batch_size = batch_size
        self._buffer: list[dict[str, Any]] = []
        self._table = None
        self._catalog = None

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "LakehouseSink":
        return cls(
            catalog_name=env.get("LAKEHOUSE_CATALOG", "rest"),
            namespace=env.get("LAKEHOUSE_NAMESPACE", "industrial"),
            table_name=env.get("LAKEHOUSE_TABLE", "events"),
            warehouse=env.get("LAKEHOUSE_WAREHOUSE", "s3://lakehouse/"),
            s3_endpoint=env.get("LAKEHOUSE_S3_ENDPOINT", "http://localhost:19000"),
            s3_access_key=env.get("LAKEHOUSE_S3_ACCESS_KEY", "minio"),
            s3_secret_key=env.get("LAKEHOUSE_S3_SECRET_KEY", "minio12345"),
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
            "s3.endpoint": self._s3_endpoint,
            "s3.access-key-id": self._s3_access_key,
            "s3.secret-access-key": self._s3_secret_key,
        }
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

            arrow_table = pa.Table.from_pylist(self._buffer)
            self._table.append(arrow_table)
            self._buffer.clear()
        except Exception as exc:  # pragma: no cover - lakehouse runtime failure
            logger.warning("lakehouse append failed: %s", exc)

    def close(self) -> None:
        self.flush()

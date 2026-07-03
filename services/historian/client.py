from __future__ import annotations

import functools
import os
import time
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values

from services.common.sql_compiler import validate_readonly_sql
from services.common.runtime_metrics import observe_historian_query


logger = logging.getLogger(__name__)

# Optional Prometheus metrics for write reliability. No-op if prometheus_client
# is unavailable so the historian client stays dependency-light.
try:
    from prometheus_client import Counter, Histogram

    historian_write_total = Counter(
        "historian_write_total",
        "Historian write attempts",
        ["table", "status"],
    )
    historian_write_latency = Histogram(
        "historian_write_latency_seconds",
        "Historian write latency",
        ["table"],
    )
except Exception:  # pragma: no cover - metrics are optional
    class _NoopMetric:
        def labels(self, *a, **k):
            return self
        def inc(self, *a, **k):
            pass
        def observe(self, *a, **k):
            pass

    historian_write_total = _NoopMetric()  # type: ignore
    historian_write_latency = _NoopMetric()  # type: ignore

WRITE_MAX_RETRIES = int(os.getenv("HISTORIAN_WRITE_MAX_RETRIES", "3"))
WRITE_BACKOFF_SECONDS = tuple(
    float(x) for x in os.getenv("HISTORIAN_WRITE_BACKOFF_SECONDS", "0.2,0.6,1.8").split(",")
)
ALLOWED_QUERY_TABLES = {"industrial_events", "processed_events", "ai_enriched", "dead_letter_events"}


def _connection_string() -> str:
    host = os.getenv("TIMESCALE_HOST", os.getenv("POSTGRES_HOST", "localhost"))
    port = os.getenv("TIMESCALE_PORT", os.getenv("POSTGRES_PORT", "15432"))
    db = os.getenv("TIMESCALE_DB", os.getenv("POSTGRES_DB", "stream_engine"))
    user = os.getenv("TIMESCALE_USER", os.getenv("POSTGRES_USER", "stream"))
    password = os.getenv("TIMESCALE_PASSWORD", os.getenv("POSTGRES_PASSWORD", "stream"))
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"




@functools.lru_cache(maxsize=1)
def _connection_pool():
    """Create a persistent connection pool for better performance."""
    import psycopg2.pool
    return psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=_connection_string(),
    )

@contextmanager
def get_connection():
    pool = _connection_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def _execute_values_write(table: str, statement: str, rows: list[tuple[Any, ...]]) -> None:
    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, statement, rows)
            conn.commit()

    _execute_with_retry(table, do_write)


def _fetch_rows(table: str, operation: str, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    start = time.monotonic()
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in cur.fetchall()]
    observe_historian_query(table, operation, time.monotonic() - start, len(rows))
    return rows


def _execute_with_retry(table: str, op: Callable[[], None]) -> None:
    """Run a DB write with retry/backoff on transient failures.

    Retries on connection/operational errors and serialization failures; logs and
    increments a failure counter so silent data loss is surfaced. Non-retryable
    errors (bad SQL / schema mismatch) raise immediately so they surface loudly.
    """
    last_exc: Exception | None = None
    for attempt in range(WRITE_MAX_RETRIES + 1):
        start = time.monotonic()
        try:
            op()
            historian_write_latency.labels(table=table).observe(time.monotonic() - start)
            historian_write_total.labels(table=table, status="ok").inc()
            return
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            last_exc = e
            logger.warning("historian write to %s failed (attempt %s): %s", table, attempt + 1, e)
            try:
                _connection_pool().closeall()
            except Exception:
                pass
            # _connection_pool is the decorated function; cache_clear is on it.
            if hasattr(_connection_pool, "cache_clear"):
                _connection_pool.cache_clear()  # type: ignore[attr-defined]
        except psycopg2.errors.SerializationFailure as e:
            last_exc = e
            logger.warning("historian write to %s serialization failure (attempt %s): %s", table, attempt + 1, e)
        if attempt < WRITE_MAX_RETRIES:
            backoff = WRITE_BACKOFF_SECONDS[min(attempt, len(WRITE_BACKOFF_SECONDS) - 1)]
            time.sleep(backoff)
    historian_write_total.labels(table=table, status="failed").inc()
    logger.error("historian write to %s permanently failed after %s attempts: %s", table, WRITE_MAX_RETRIES + 1, last_exc)
    raise last_exc  # type: ignore[misc]


def insert_industrial_event(event: dict[str, Any]) -> None:
    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO industrial_events (
                        time, event_id, source_protocol, source_id, asset_id, tag,
                        value, quality, unit, site, line, schema_version,
                        fault_type, scenario_id, ground_truth_severity, step
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.get("ts_ingest", datetime.now(timezone.utc).isoformat()),
                        event.get("event_id"),
                        event.get("source_protocol"),
                        event.get("source_id"),
                        event.get("asset_id"),
                        event.get("tag"),
                        float(event.get("value", 0)),
                        event.get("quality", "good"),
                        event.get("unit"),
                        event.get("site", "demo-site"),
                        event.get("line", "line-01"),
                        event.get("schema_version", 1),
                        event.get("fault_type", "normal"),
                        event.get("scenario_id", "sc-000"),
                        event.get("ground_truth_severity", "normal"),
                        event.get("step", 0),
                    ),
                )
            conn.commit()

    _execute_with_retry("industrial_events", do_write)


def insert_industrial_events(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    rows = [
        (
            event.get("ts_ingest", datetime.now(timezone.utc).isoformat()),
            event.get("event_id"),
            event.get("source_protocol"),
            event.get("source_id"),
            event.get("asset_id"),
            event.get("tag"),
            float(event.get("value", 0)),
            event.get("quality", "good"),
            event.get("unit"),
            event.get("site", "demo-site"),
            event.get("line", "line-01"),
            event.get("schema_version", 1),
            event.get("fault_type", "normal"),
            event.get("scenario_id", "sc-000"),
            event.get("ground_truth_severity", "normal"),
            event.get("step", 0),
        )
        for event in events
    ]
    _execute_values_write(
        "industrial_events",
        """
        INSERT INTO industrial_events (
            time, event_id, source_protocol, source_id, asset_id, tag,
            value, quality, unit, site, line, schema_version,
            fault_type, scenario_id, ground_truth_severity, step
        ) VALUES %s
        """,
        rows,
    )


def insert_processed_event(event: dict[str, Any]) -> None:
    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO processed_events (
                        time, event_id, device_id, asset_id, tag, value, unit,
                        site_id, source_protocol, quality,
                        schema_version, temperature_c, vibration_mm_s, pressure_bar,
                        processed_at, window_size, temperature_avg_c, vibration_avg_mm_s,
                        anomaly_score, severity, triggered_rules, baseline, evaluation
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        event.get("event_id"),
                        event.get("device_id"),
                        event.get("asset_id", event.get("device_id")),
                        event.get("tag", ""),
                        float(event.get("value", 0) or 0),
                        event.get("unit", ""),
                        event.get("site_id"),
                        event.get("source_protocol"),
                        event.get("quality"),
                        event.get("schema_version", 1),
                        float(event.get("temperature_c", 0)),
                        float(event.get("vibration_mm_s", 0)),
                        float(event.get("pressure_bar", 0)),
                        event.get("processed_at"),
                        event.get("window_size", 0),
                        event.get("temperature_avg_c", 0),
                        event.get("vibration_avg_mm_s", 0),
                        event.get("anomaly_score", 0),
                        event.get("severity", "normal"),
                        list(event.get("triggered_rules") or []),
                        Json(event.get("baseline")),
                        Json(event.get("evaluation")),
                    ),
                )
            conn.commit()

    _execute_with_retry("processed_events", do_write)


def insert_processed_events(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    rows = [
        (
            event.get("timestamp", datetime.now(timezone.utc).isoformat()),
            event.get("event_id"),
            event.get("device_id"),
            event.get("asset_id", event.get("device_id")),
            event.get("tag", ""),
            float(event.get("value", 0) or 0),
            event.get("unit", ""),
            event.get("site_id"),
            event.get("source_protocol"),
            event.get("quality"),
            event.get("schema_version", 1),
            float(event.get("temperature_c", 0)),
            float(event.get("vibration_mm_s", 0)),
            float(event.get("pressure_bar", 0)),
            event.get("processed_at"),
            event.get("window_size", 0),
            event.get("temperature_avg_c", 0),
            event.get("vibration_avg_mm_s", 0),
            event.get("anomaly_score", 0),
            event.get("severity", "normal"),
            list(event.get("triggered_rules") or []),
            Json(event.get("baseline")),
            Json(event.get("evaluation")),
        )
        for event in events
    ]
    _execute_values_write(
        "processed_events",
        """
        INSERT INTO processed_events (
            time, event_id, device_id, asset_id, tag, value, unit,
            site_id, source_protocol, quality,
            schema_version, temperature_c, vibration_mm_s, pressure_bar,
            processed_at, window_size, temperature_avg_c, vibration_avg_mm_s,
            anomaly_score, severity, triggered_rules, baseline, evaluation
        ) VALUES %s
        """,
        rows,
    )


def insert_ai_enriched(event: dict[str, Any]) -> None:
    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_enriched (
                        time, source, model, batch_size, summary, latency_seconds
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        event.get("source"),
                        event.get("model"),
                        event.get("batch_size", 0),
                        event.get("summary", ""),
                        event.get("latency_seconds", 0),
                    ),
                )
            conn.commit()

    _execute_with_retry("ai_enriched", do_write)



def insert_dead_letter(event: dict[str, Any]) -> None:
    """Persist a dead-letter (validation-failed) event so it can be inspected/replayed."""

    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dead_letter_events (
                        time, event_id, source_protocol, source_id,
                        error, payload, schema_version, origin
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.get("ts_ingest", datetime.now(timezone.utc).isoformat()),
                        event.get("event_id"),
                        event.get("source_protocol"),
                        event.get("source_id"),
                        event.get("error"),
                        Json(event.get("payload")),
                        event.get("schema_version", 1),
                        event.get("origin", "unknown"),
                    ),
                )
            conn.commit()

    _execute_with_retry("dead_letter_events", do_write)


def query_recent_events(table: str, limit: int = 100) -> list[dict[str, Any]]:
    if table not in ALLOWED_QUERY_TABLES:
        raise ValueError(f"unsupported table: {table}")
    return _fetch_rows(table, "recent_events", f"SELECT * FROM {table} ORDER BY time DESC LIMIT %s", (limit,))




def query_sql(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return _fetch_rows("sql", "readwrite", sql, params)


def query_sql_readonly(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    safety = validate_readonly_sql(sql)
    if not safety.allowed:
        raise ValueError(safety.reason or "readonly sql rejected")
    return _fetch_rows("sql", "readonly", sql, params)




def query_tables() -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            return [row[0] for row in cur.fetchall()]


def query_trend(asset_id: str, tag: str, hours: int = 1) -> list[dict[str, Any]]:
    return _fetch_rows(
        "industrial_events",
        "trend",
        """
        SELECT time, value, quality, fault_type, ground_truth_severity
        FROM industrial_events
        WHERE asset_id = %s AND tag = %s
          AND time > NOW() - INTERVAL '%s hours'
        ORDER BY time ASC
        """,
        (asset_id, tag, hours),
    )
def query_alarms(limit: int = 50) -> list[dict[str, Any]]:
    rows = _fetch_rows(
        "processed_events",
        "alarms",
        """
        SELECT time, asset_id, tag, severity, triggered_rules, evaluation
        FROM processed_events
        WHERE severity IN ('warning', 'critical')
        ORDER BY time DESC
        LIMIT %s
        """,
        (limit,),
    )
    return [
        {
            "time": row["time"],
            "asset_id": row["asset_id"],
            "tag": row["tag"],
            "severity": row["severity"],
            "message": f"Anomaly detected on {row['asset_id']}.{row['tag']}",
            "triggered_rules": row.get("triggered_rules", []),
            "acknowledged": False,
        }
        for row in rows
    ]


# Data retention and compression policies
import logging
logger = logging.getLogger(__name__)


def setup_retention_policies() -> None:
    """Configure TimescaleDB compression and retention policies.

    - Compress data older than 7 days
    - Drop raw data older than 90 days
    - Keep processed events for 1 year
    - Keep AI enriched events for 2 years
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Enable compression on hypertables
            # segmentby columns must actually exist on each table.
            compress_segmentby = {
                "industrial_events": "asset_id, tag",
                "processed_events": "asset_id, tag",
                "ai_enriched": "source, model",
            }
            for table in ["industrial_events", "processed_events", "ai_enriched"]:
                try:
                    cur.execute(f"""
                        ALTER TABLE {table} SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = '{compress_segmentby[table]}'
                        );
                    """)
                    logger.info(f"Compression enabled for {table}")
                except psycopg2.Error as e:
                    logger.warning(f"Compression may already be enabled for {table}: {e}")
                    conn.rollback()

                # Add compression policy (compress after 7 days)
                try:
                    cur.execute(f"""
                        SELECT add_compression_policy('{table}', INTERVAL '7 days');
                    """)
                    logger.info(f"Compression policy added for {table}")
                except psycopg2.Error as e:
                    logger.warning(f"Compression policy may already exist for {table}: {e}")
                    conn.rollback()

                # Add retention policy
                retention_days = 90 if table == "industrial_events" else 365 if table == "processed_events" else 730
                try:
                    cur.execute(f"""
                        SELECT add_retention_policy('{table}', INTERVAL '{retention_days} days');
                    """)
                    logger.info(f"Retention policy ({retention_days} days) added for {table}")
                except psycopg2.Error as e:
                    logger.warning(f"Retention policy may already exist for {table}: {e}")
                    conn.rollback()

        conn.commit()


def get_storage_stats() -> dict[str, Any]:
    """Return storage statistics for all hypertables."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    hypertable_name,
                    num_chunks,
                    table_size,
                    index_size,
                    total_size
                FROM timescaledb_information.hypertables
                ORDER BY hypertable_name;
            """)
            hypertables = [dict(row) for row in cur.fetchall()]

            cur.execute("""
                SELECT
                    hypertable_name,
                    chunk_name,
                    compression_status,
                    before_compression_total_bytes,
                    after_compression_total_bytes
                FROM timescaledb_information.chunks
                WHERE compression_status = 'Compressed'
                ORDER BY hypertable_name;
            """)
            compressed = [dict(row) for row in cur.fetchall()]

            return {
                "hypertables": hypertables,
                "compressed_chunks": compressed,
                "compression_ratio": _calculate_compression_ratio(compressed),
            }


def _calculate_compression_ratio(compressed: list[dict]) -> float:
    if not compressed:
        return 1.0
    total_before = sum(row.get("before_compression_total_bytes", 0) or 0 for row in compressed)
    total_after = sum(row.get("after_compression_total_bytes", 0) or 0 for row in compressed)
    if total_after == 0:
        return 1.0
    return round(total_before / total_after, 2)


def manual_compress_chunk(table: str, older_than_days: int = 7) -> dict[str, Any]:
    """Manually compress chunks older than specified days."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT chunk_name, range_start, range_end
                FROM timescaledb_information.chunks
                WHERE hypertable_name = %s
                  AND range_end < NOW() - INTERVAL '%s days'
                  AND compression_status = 'Uncompressed'
                ORDER BY range_start;
            """, (table, older_than_days))
            chunks = [dict(row) for row in cur.fetchall()]

            compressed = 0
            for chunk in chunks:
                try:
                    cur.execute(f"SELECT compress_chunk('_timescaledb_internal.{chunk['chunk_name']}');")
                    compressed += 1
                except psycopg2.Error as e:
                    logger.warning(f"Failed to compress {chunk['chunk_name']}: {e}")
                    conn.rollback()

            conn.commit()
            return {
                "table": table,
                "chunks_found": len(chunks),
                "chunks_compressed": compressed,
            }

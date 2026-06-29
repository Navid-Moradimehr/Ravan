from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


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


def insert_industrial_event(event: dict[str, Any]) -> None:
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


def insert_processed_event(event: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO processed_events (
                    time, event_id, device_id, site_id, source_protocol, quality,
                    schema_version, temperature_c, vibration_mm_s, pressure_bar,
                    processed_at, window_size, temperature_avg_c, vibration_avg_mm_s,
                    anomaly_score, severity, triggered_rules, baseline, evaluation
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    event.get("event_id"),
                    event.get("device_id"),
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
                    event.get("triggered_rules", []),
                    event.get("baseline"),
                    event.get("evaluation"),
                ),
            )
        conn.commit()


def insert_ai_enriched(event: dict[str, Any]) -> None:
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


def query_recent_events(table: str, limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM {table} ORDER BY time DESC LIMIT %s",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]




def query_sql(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]




def query_tables() -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            return [row[0] for row in cur.fetchall()]


def query_trend(asset_id: str, tag: str, hours: int = 1) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT time, value, quality, fault_type, ground_truth_severity
                FROM industrial_events
                WHERE asset_id = %s AND tag = %s
                  AND time > NOW() - INTERVAL '%s hours'
                ORDER BY time ASC
                """,
                (asset_id, tag, hours),
            )
            return [dict(row) for row in cur.fetchall()]
def query_alarms(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT time, asset_id, tag, severity, triggered_rules, evaluation
                FROM processed_events
                WHERE severity IN ('warning', 'critical')
                ORDER BY time DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
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
            for table in ["industrial_events", "processed_events", "ai_enriched"]:
                try:
                    cur.execute(f"""
                        ALTER TABLE {table} SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = 'asset_id, tag'
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

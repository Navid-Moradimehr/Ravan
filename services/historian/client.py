from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


def _connection_string() -> str:
    host = os.getenv("TIMESCALE_HOST", "localhost")
    port = os.getenv("TIMESCALE_PORT", "15433")
    db = os.getenv("TIMESCALE_DB", "stream_engine")
    user = os.getenv("TIMESCALE_USER", "stream")
    password = os.getenv("TIMESCALE_PASSWORD", "stream")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@contextmanager
def get_connection():
    conn = psycopg2.connect(_connection_string())
    try:
        yield conn
    finally:
        conn.close()


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

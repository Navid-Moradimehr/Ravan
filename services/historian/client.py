from __future__ import annotations

import functools
import os
import time
import logging
import uuid
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values

from services.common.semantic_core import (
    OntologyPack,
    SemanticAction,
    SemanticDocument,
    SemanticEntity,
    SemanticEvent,
    SemanticGraph,
    SemanticLocation,
    SemanticMeasurement,
    SemanticObservation,
    SemanticRelationship,
    SemanticState,
    SemanticWorkflow,
)
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
DEFAULT_QUERY_TIMEOUT_MS = int(os.getenv("HISTORIAN_QUERY_TIMEOUT_MS", "15000"))
ALLOWED_QUERY_TABLES = {"industrial_events", "processed_events", "ai_enriched", "dead_letter_events"}
SEMANTIC_TABLES = {
    "semantic_ontology_packs",
    "semantic_entities",
    "semantic_relationships",
    "semantic_measurements",
    "semantic_observations",
    "semantic_actions",
    "semantic_documents",
    "semantic_locations",
    "semantic_states",
    "semantic_workflows",
    "semantic_events",
    "semantic_lineage",
}


@dataclass(slots=True)
class HistorianQueryHandle:
    query_id: str
    connection: Any
    started_at: float
    timeout_ms: int
    operation: str
    sql: str


_QUERY_LOCK = Lock()
_ACTIVE_QUERIES: dict[str, HistorianQueryHandle] = {}


def _connection_string() -> str:
    host = os.getenv("TIMESCALE_HOST", os.getenv("POSTGRES_HOST", "localhost"))
    port = os.getenv("TIMESCALE_PORT", os.getenv("POSTGRES_PORT", "15432"))
    db = os.getenv("TIMESCALE_DB", os.getenv("POSTGRES_DB", "stream_engine"))
    user = os.getenv("TIMESCALE_USER", os.getenv("POSTGRES_USER", "stream"))
    password = os.getenv("TIMESCALE_PASSWORD", os.getenv("POSTGRES_PASSWORD", "stream"))
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def _coalesce_timestamp(value: Any | None) -> str:
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()




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
                execute_values(cur, statement, rows, page_size=len(rows))
            conn.commit()

    _execute_with_retry(table, do_write)


def _fetch_rows(table: str, operation: str, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return _fetch_rows_with_timeout(table, operation, query, params, query_id=None, timeout_ms=None)


def _register_query_handle(handle: HistorianQueryHandle) -> None:
    with _QUERY_LOCK:
        _ACTIVE_QUERIES[handle.query_id] = handle


def _release_query_handle(query_id: str) -> None:
    with _QUERY_LOCK:
        _ACTIVE_QUERIES.pop(query_id, None)


def cancel_historian_query(query_id: str) -> dict[str, Any]:
    with _QUERY_LOCK:
        handle = _ACTIVE_QUERIES.get(query_id)
    if handle is None:
        return {"query_id": query_id, "status": "not_found"}

    try:
        handle.connection.cancel()
    except Exception as exc:
        logger.warning("historian query cancel failed for %s: %s", query_id, exc)
        return {"query_id": query_id, "status": "cancel_failed", "error": str(exc)}

    logger.info(
        "historian query cancel requested query_id=%s operation=%s timeout_ms=%s",
        query_id,
        handle.operation,
        handle.timeout_ms,
    )
    return {"query_id": query_id, "status": "cancel_requested"}


class HistorianQueryTimeoutError(TimeoutError):
    pass


class HistorianQueryCancelledError(RuntimeError):
    pass


def _fetch_rows_with_timeout(
    table: str,
    operation: str,
    query: str,
    params: tuple[Any, ...],
    *,
    query_id: str | None,
    timeout_ms: int | None,
) -> list[dict[str, Any]]:
    start = time.monotonic()
    query_id = query_id or uuid.uuid4().hex
    timeout_ms = DEFAULT_QUERY_TIMEOUT_MS if timeout_ms is None else max(1, int(timeout_ms))

    with get_connection() as conn:
        handle = HistorianQueryHandle(
            query_id=query_id,
            connection=conn,
            started_at=start,
            timeout_ms=timeout_ms,
            operation=operation,
            sql=query,
        )
        _register_query_handle(handle)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT set_config('statement_timeout', %s, true)", (f"{timeout_ms}ms",))
                cur.execute(query, params)
                rows = [dict(row) for row in cur.fetchall()]
        except psycopg2.errors.QueryCanceled as exc:
            message = str(exc).lower()
            if "timeout" in message or "statement timeout" in message:
                raise HistorianQueryTimeoutError(
                    f"Historian query timed out after {timeout_ms} ms"
                ) from exc
            raise HistorianQueryCancelledError(f"Historian query {query_id} was cancelled") from exc
        finally:
            _release_query_handle(query_id)

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
                    ON CONFLICT (time, event_id) DO NOTHING
                    """,
                    (
                        _coalesce_timestamp(event.get("ts_source") or event.get("ts_ingest")),
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
    rows = []
    for event in events:
        rows.append(
            (
                _coalesce_timestamp(event.get("ts_ingest")),
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
        )
    _execute_values_write(
        "industrial_events",
        """
        INSERT INTO industrial_events (
            time, event_id, source_protocol, source_id, asset_id, tag,
            value, quality, unit, site, line, schema_version,
            fault_type, scenario_id, ground_truth_severity, step
        ) VALUES %s
        ON CONFLICT (time, event_id) DO NOTHING
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
                    ON CONFLICT (time, event_id) DO NOTHING
                    """,
                    (
                        _coalesce_timestamp(event.get("timestamp")),
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
    rows = []
    for event in events:
        rows.append(
            (
                _coalesce_timestamp(event.get("timestamp")),
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
        )
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
        ON CONFLICT (time, event_id) DO NOTHING
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
                        _coalesce_timestamp(None),
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
                    ON CONFLICT (time, event_id) DO NOTHING
                    """,
                    (
                        _coalesce_timestamp(event.get("ts_ingest")),
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




def query_sql(sql: str, params: tuple = (), *, query_id: str | None = None, timeout_ms: int | None = None) -> list[dict[str, Any]]:
    return _fetch_rows_with_timeout("sql", "readwrite", sql, params, query_id=query_id, timeout_ms=timeout_ms)


def query_sql_readonly(
    sql: str,
    params: tuple = (),
    *,
    query_id: str | None = None,
    timeout_ms: int | None = None,
) -> list[dict[str, Any]]:
    safety = validate_readonly_sql(sql)
    if not safety.allowed:
        raise ValueError(safety.reason or "readonly sql rejected")
    return _fetch_rows_with_timeout("sql", "readonly", sql, params, query_id=query_id, timeout_ms=timeout_ms)




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


def _semantic_rows(table: str, order_by: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    if table not in SEMANTIC_TABLES:
        raise ValueError(f"unsupported semantic table: {table}")
    sql = f"SELECT * FROM {table}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT %s"
        params = (limit,)
    return _fetch_rows(table, "semantic_read", sql, params)


def _semantic_upsert(
    table: str,
    key_column: str,
    row: dict[str, Any],
    *,
    json_columns: set[str] | None = None,
) -> dict[str, Any]:
    json_columns = json_columns or set()
    columns = list(row.keys())
    if key_column not in columns:
        raise ValueError(f"{table} upsert requires key column {key_column}")
    values = [Json(row[column]) if column in json_columns else row[column] for column in columns]
    updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != key_column)
    if updates:
        updates = f"{updates}, updated_at = NOW()"
    statement = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join(["%s"] * len(columns))})
        ON CONFLICT ({key_column}) DO UPDATE SET
            {updates}
    """
    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(statement, values)
            conn.commit()

    _execute_with_retry(table, do_write)
    return row


def replace_semantic_graph(graph: Any) -> None:
    from services.common.semantic_core import SemanticGraph

    if not isinstance(graph, SemanticGraph):
        raise TypeError("graph must be a SemanticGraph")

    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for table in (
                    "semantic_events",
                    "semantic_workflows",
                    "semantic_states",
                    "semantic_locations",
                    "semantic_documents",
                    "semantic_actions",
                    "semantic_observations",
                    "semantic_measurements",
                    "semantic_relationships",
                    "semantic_entities",
                    "semantic_ontology_packs",
                ):
                    cur.execute(f"DELETE FROM {table}")

                for pack in graph.ontology_packs:
                    cur.execute(
                        """
                        INSERT INTO semantic_ontology_packs (
                            pack_id, name, layer, version, concepts, notes, metadata, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (pack_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            layer = EXCLUDED.layer,
                            version = EXCLUDED.version,
                            concepts = EXCLUDED.concepts,
                            notes = EXCLUDED.notes,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        """,
                        (
                            pack.pack_id,
                            pack.name,
                            pack.layer,
                            pack.version,
                            list(pack.concepts),
                            list(pack.notes),
                            Json({}),
                        ),
                    )

                def _insert_many(table: str, rows: list[tuple[Any, ...]], statement: str) -> None:
                    if rows:
                        execute_values(cur, statement, rows, page_size=len(rows))

                _insert_many(
                    "semantic_entities",
                    [
                        (
                            entity.entity_id,
                            entity.entity_type,
                            entity.name,
                            list(entity.labels),
                            Json(entity.metadata),
                        )
                        for entity in graph.entities.values()
                    ],
                    """
                    INSERT INTO semantic_entities (
                        entity_id, entity_type, name, labels, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_relationships",
                    [
                        (
                            relationship.relationship_id,
                            relationship.source_id,
                            relationship.target_id,
                            relationship.relationship_type,
                            Json(relationship.metadata),
                        )
                        for relationship in graph.relationships.values()
                    ],
                    """
                    INSERT INTO semantic_relationships (
                        relationship_id, source_id, target_id, relationship_type, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_measurements",
                    [
                        (
                            measurement.measurement_id,
                            measurement.entity_id,
                            measurement.name,
                            measurement.unit,
                            measurement.minimum,
                            measurement.maximum,
                            measurement.warning_low,
                            measurement.warning_high,
                            measurement.critical_low,
                            measurement.critical_high,
                            measurement.sampling_rate_hz,
                            Json(measurement.metadata),
                        )
                        for measurement in graph.measurements.values()
                    ],
                    """
                    INSERT INTO semantic_measurements (
                        measurement_id, entity_id, name, unit, minimum, maximum,
                        warning_low, warning_high, critical_low, critical_high,
                        sampling_rate_hz, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_observations",
                    [
                        (
                            observation.observation_id,
                            observation.entity_id,
                            observation.observed_at,
                            Json(observation.value),
                            observation.source_id,
                            Json(observation.metadata),
                        )
                        for observation in graph.observations.values()
                    ],
                    """
                    INSERT INTO semantic_observations (
                        observation_id, entity_id, observed_at, value, source_id, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_actions",
                    [
                        (
                            action.action_id,
                            action.actor_id,
                            action.target_id,
                            action.action_type,
                            action.occurred_at,
                            Json(action.metadata),
                        )
                        for action in graph.actions.values()
                    ],
                    """
                    INSERT INTO semantic_actions (
                        action_id, actor_id, target_id, action_type, occurred_at, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_documents",
                    [
                        (
                            document.document_id,
                            document.title,
                            document.document_type,
                            document.uri,
                            Json(document.metadata),
                        )
                        for document in graph.documents.values()
                    ],
                    """
                    INSERT INTO semantic_documents (
                        document_id, title, document_type, uri, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_locations",
                    [
                        (
                            location.location_id,
                            location.name,
                            location.location_type,
                            location.parent_id,
                            Json(location.metadata),
                        )
                        for location in graph.locations.values()
                    ],
                    """
                    INSERT INTO semantic_locations (
                        location_id, name, location_type, parent_id, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_states",
                    [
                        (
                            state.state_id,
                            state.entity_id,
                            state.state,
                            state.valid_from,
                            state.valid_to,
                            Json(state.metadata),
                        )
                        for state in graph.states.values()
                    ],
                    """
                    INSERT INTO semantic_states (
                        state_id, entity_id, state, valid_from, valid_to, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_workflows",
                    [
                        (
                            workflow.workflow_id,
                            workflow.name,
                            workflow.workflow_type,
                            Json(workflow.metadata),
                        )
                        for workflow in graph.workflows.values()
                    ],
                    """
                    INSERT INTO semantic_workflows (
                        workflow_id, name, workflow_type, metadata, updated_at
                    ) VALUES %s
                    """,
                )
                _insert_many(
                    "semantic_events",
                    [
                        (
                            event.event_id,
                            event.event_type,
                            event.occurred_at,
                            event.source_id,
                            event.entity_id,
                            Json(event.payload),
                            Json(event.metadata),
                        )
                        for event in graph.events.values()
                    ],
                    """
                    INSERT INTO semantic_events (
                        event_id, event_type, occurred_at, source_id, entity_id, payload, metadata, updated_at
                    ) VALUES %s
                    """,
                )
            conn.commit()

    _execute_with_retry("semantic_graph", do_write)


def load_semantic_graph() -> dict[str, Any]:
    graph = SemanticGraph.default()
    packs = [
        OntologyPack(
            pack_id=str(row["pack_id"]),
            name=str(row["name"]),
            layer=str(row["layer"]),
            version=str(row["version"]),
            concepts=tuple(row.get("concepts") or []),
            notes=tuple(row.get("notes") or []),
        )
        for row in _semantic_rows("semantic_ontology_packs", "pack_id ASC")
    ]
    if packs:
        graph.ontology_packs = packs
    graph.entities = {
        str(row["entity_id"]): SemanticEntity(
            entity_id=str(row["entity_id"]),
            entity_type=str(row["entity_type"]),
            name=str(row.get("name", "")),
            labels=tuple(row.get("labels") or []),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_entities", "entity_id ASC")
    }
    graph.relationships = {
        str(row["relationship_id"]): SemanticRelationship(
            relationship_id=str(row["relationship_id"]),
            source_id=str(row["source_id"]),
            target_id=str(row["target_id"]),
            relationship_type=str(row["relationship_type"]),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_relationships", "relationship_id ASC")
    }
    graph.measurements = {
        str(row["measurement_id"]): SemanticMeasurement(
            measurement_id=str(row["measurement_id"]),
            entity_id=str(row["entity_id"]),
            name=str(row.get("name", "")),
            unit=str(row.get("unit", "")),
            minimum=row.get("minimum"),
            maximum=row.get("maximum"),
            warning_low=row.get("warning_low"),
            warning_high=row.get("warning_high"),
            critical_low=row.get("critical_low"),
            critical_high=row.get("critical_high"),
            sampling_rate_hz=row.get("sampling_rate_hz"),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_measurements", "measurement_id ASC")
    }
    graph.observations = {
        str(row["observation_id"]): SemanticObservation(
            observation_id=str(row["observation_id"]),
            entity_id=str(row["entity_id"]),
            observed_at=str(row["observed_at"]),
            value=row.get("value"),
            source_id=str(row.get("source_id", "")),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_observations", "observed_at DESC, observation_id ASC")
    }
    graph.actions = {
        str(row["action_id"]): SemanticAction(
            action_id=str(row["action_id"]),
            actor_id=str(row["actor_id"]),
            target_id=str(row["target_id"]),
            action_type=str(row["action_type"]),
            occurred_at=str(row["occurred_at"]),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_actions", "occurred_at DESC, action_id ASC")
    }
    graph.documents = {
        str(row["document_id"]): SemanticDocument(
            document_id=str(row["document_id"]),
            title=str(row["title"]),
            document_type=str(row.get("document_type", "document")),
            uri=str(row.get("uri", "")),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_documents", "document_id ASC")
    }
    graph.locations = {
        str(row["location_id"]): SemanticLocation(
            location_id=str(row["location_id"]),
            name=str(row["name"]),
            location_type=str(row.get("location_type", "location")),
            parent_id=row.get("parent_id"),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_locations", "location_id ASC")
    }
    graph.states = {
        str(row["state_id"]): SemanticState(
            state_id=str(row["state_id"]),
            entity_id=str(row["entity_id"]),
            state=str(row["state"]),
            valid_from=str(row["valid_from"]),
            valid_to=row.get("valid_to"),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_states", "valid_from DESC, state_id ASC")
    }
    graph.workflows = {
        str(row["workflow_id"]): SemanticWorkflow(
            workflow_id=str(row["workflow_id"]),
            name=str(row["name"]),
            workflow_type=str(row.get("workflow_type", "workflow")),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_workflows", "workflow_id ASC")
    }
    graph.events = {
        str(row["event_id"]): SemanticEvent(
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            occurred_at=str(row["occurred_at"]),
            source_id=str(row.get("source_id", "")),
            entity_id=str(row.get("entity_id", "")),
            payload=dict(row.get("payload") or {}),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in _semantic_rows("semantic_events", "occurred_at DESC, event_id ASC")
    }
    return graph.to_dict()


def upsert_semantic_lineage(record: dict[str, Any]) -> dict[str, Any]:
    row = {
        "lineage_id": record["lineage_id"],
        "kind": record.get("kind", "unknown"),
        "source_id": record.get("source_id", ""),
        "target_id": record.get("target_id", ""),
        "entity_id": record.get("entity_id", ""),
        "relationship_id": record.get("relationship_id", ""),
        "site_id": record.get("site_id", ""),
        "dataset_id": record.get("dataset_id", ""),
        "model_version": record.get("model_version", ""),
        "processing_version": record.get("processing_version", ""),
        "occurred_at": record.get("occurred_at") or _utc_now(),
        "metadata": record.get("metadata", {}),
    }
    return _semantic_upsert("semantic_lineage", "lineage_id", row, json_columns={"metadata"})


def list_semantic_lineage(*, site_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = _semantic_rows("semantic_lineage", "occurred_at DESC, lineage_id DESC")
    if site_id:
        rows = [row for row in rows if str(row.get("site_id", "")).lower() == site_id.lower()]
    return rows[: max(1, limit)]


def insert_audit_log(event: dict[str, Any]) -> dict[str, Any]:
    row = (
        event.get("time") or _utc_now(),
        event.get("user_id", ""),
        event.get("action", ""),
        event.get("resource", ""),
        Json(event.get("details", {})),
    )

    def do_write() -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (time, user_id, action, resource, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    row,
                )
            conn.commit()

    _execute_with_retry("audit_logs", do_write)
    return {
        "time": row[0],
        "user_id": row[1],
        "action": row[2],
        "resource": row[3],
        "details": event.get("details", {}),
    }


# Data retention and compression policies
import logging
logger = logging.getLogger(__name__)


def setup_unique_indexes() -> None:
    """Create idempotent unique indexes for event-id deduplication.

    The edge publisher now writes only to Kafka; the normalized fan-out consumer
    persists to the historian. With at-least-once delivery, replayed batches can
    re-insert the same ``event_id`` at the same source timestamp. A unique index
    plus ``ON CONFLICT DO NOTHING`` turns those replays into no-ops instead of
    duplicate rows. This is idempotent (``IF NOT EXISTS``) and safe to call on
    startup.
    """
    unique_indexes = {
        "industrial_events": "industrial_events_event_id_uniq",
        "processed_events": "processed_events_event_id_uniq",
        "dead_letter_events": "dead_letter_events_event_id_uniq",
    }
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table, index_name in unique_indexes.items():
                try:
                    cur.execute(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                        f"ON {table} (time, event_id);"
                    )
                    logger.info("unique index ensured for %s", table)
                except psycopg2.Error as exc:
                    logger.warning("could not ensure unique index for %s: %s", table, exc)
                    conn.rollback()
        conn.commit()


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

            def _log_policy_message(prefix: str, table: str, exc: psycopg2.Error) -> None:
                message = str(exc).lower()
                if "already exists" in message or "already enabled" in message:
                    logger.debug("%s for %s already exists", prefix, table)
                else:
                    logger.warning("%s for %s failed: %s", prefix, table, exc)

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
                    _log_policy_message("Compression", table, e)
                    conn.rollback()

                # Add compression policy (compress after 7 days)
                try:
                    cur.execute(f"""
                        SELECT add_compression_policy('{table}', INTERVAL '7 days');
                    """)
                    logger.info(f"Compression policy added for {table}")
                except psycopg2.Error as e:
                    _log_policy_message("Compression policy", table, e)
                    conn.rollback()

                # Add retention policy
                retention_days = 90 if table == "industrial_events" else 365 if table == "processed_events" else 730
                try:
                    cur.execute(f"""
                        SELECT add_retention_policy('{table}', INTERVAL '{retention_days} days');
                    """)
                    logger.info(f"Retention policy ({retention_days} days) added for {table}")
                except psycopg2.Error as e:
                    _log_policy_message("Retention policy", table, e)
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

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any

import httpx
from confluent_kafka import Consumer, Producer, TopicPartition
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response
from fastapi.responses import StreamingResponse

from services.ai_gateway.config import Settings
from services.ai_gateway.providers import (
    LLMProviderClient,
    build_fallback_summary,
    build_industrial_prompt,
)
from services.common.ai_event_contract import build_ai_summary_event, DEFAULT_AI_PROMPT_TEMPLATE_ID
from services.common.prompt_registry import prompt_registry
from services.common.structured_output import validate_industrial_summary
from services.common.service_health import ServiceHealthState
from services.common.runtime_metrics import set_consumer_lag
from services.common.ai_reporting import AIReportingPolicy, SustainedAnomalyTracker, complete_report_job, create_report_job, fail_report_job, get_policy


settings = Settings()
llm_client = LLMProviderClient(settings)
consumed_events = Counter("ai_gateway_consumed_events_total", "Processed events consumed by AI gateway")
enriched_events = Counter("ai_gateway_enriched_events_total", "AI enriched batches emitted")
llm_latency = Histogram("ai_gateway_llm_request_seconds", "LLM request latency in seconds")
batch_size_gauge = Gauge("ai_gateway_batch_size", "Most recent LLM batch size")
batch_severity_total = Counter(
    "ai_gateway_batch_severity_total",
    "Processed events emitted to the AI gateway grouped by severity",
    ["severity"],
)
last_success_epoch = Gauge("ai_gateway_last_success_epoch", "Unix timestamp of last successful enrichment")
report_queue_depth = Gauge("ai_gateway_report_queue_depth", "AI report jobs waiting for model execution")
report_workers_active = Gauge("ai_gateway_report_workers_active", "AI report workers currently executing")
report_jobs_enqueued = Counter("ai_gateway_report_jobs_enqueued_total", "AI report jobs accepted by the bounded queue")
report_jobs_completed = Counter("ai_gateway_report_jobs_completed_total", "AI report jobs completed")
report_jobs_failed = Counter("ai_gateway_report_jobs_failed_total", "AI report jobs that failed or were rejected")
service_state = ServiceHealthState(name="ai-gateway")
telemetry_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
_policy_cache: tuple[float, AIReportingPolicy] | None = None


def _append_bounded_evidence(
    batch: list[tuple[str, int, int, dict[str, Any]]],
    item: tuple[str, int, int, dict[str, Any]],
    max_events: int,
) -> None:
    """Retain only the evidence window needed by the next scheduled report."""

    batch.append(item)
    if len(batch) > max_events:
        del batch[:-max_events]


@dataclass(slots=True)
class ReportWorkItem:
    batch: list[tuple[str, int, int, dict[str, Any]]]
    policy: AIReportingPolicy
    job: dict[str, Any] | None
    offsets: list[TopicPartition]


async def report_worker(
    queue: asyncio.Queue[ReportWorkItem | None],
    producer: Producer,
    consumer: Consumer,
) -> None:
    """Execute model calls outside the Kafka poll loop.

    Queue capacity and worker count are deployment controls. The default is one
    worker because local GPU servers commonly run one model request at a time;
    increasing it is safe only when the model server and memory budget support
    concurrent requests.
    """
    while service_state.running:
        item = await queue.get()
        if item is None:
            queue.task_done()
            return
        report_workers_active.inc()
        try:
            success = await enrich_batch(item.batch, producer, policy=item.policy, job=item.job)
            if success:
                if item.job:
                    complete_report_job(str(item.job["job_id"]), {"event_id": "emitted"})
                report_jobs_completed.inc()
                consumer.commit(offsets=item.offsets, asynchronous=False)
            elif item.job:
                fail_report_job(str(item.job["job_id"]), "AI output was not acknowledged")
                report_jobs_failed.inc()
        except Exception as exc:
            service_state.mark_degraded("AI report worker failed", str(exc))
            if item.job:
                fail_report_job(str(item.job["job_id"]), str(exc))
            report_jobs_failed.inc()
        finally:
            report_workers_active.dec()
            queue.task_done()
            report_queue_depth.set(queue.qsize())


async def enqueue_report(queue: asyncio.Queue[ReportWorkItem | None], item: ReportWorkItem) -> bool:
    """Enqueue without allowing a slow model to grow memory without a bound."""
    try:
        queue.put_nowait(item)
        report_jobs_enqueued.inc()
        report_queue_depth.set(queue.qsize())
        return True
    except asyncio.QueueFull:
        if item.job:
            fail_report_job(str(item.job["job_id"]), "AI report queue is full", retry_after_seconds=30)
        report_jobs_failed.inc()
        service_state.mark_degraded("AI report queue full", "increase capacity or reduce report frequency")
        return False


def reporting_policy() -> AIReportingPolicy:
    """Reload policy periodically while retaining the pre-migration fallback."""
    global _policy_cache
    now = time.monotonic()
    if _policy_cache is None or now - _policy_cache[0] >= 10:
        try:
            _policy_cache = (now, get_policy("*"))
        except Exception as exc:  # pragma: no cover - deployment failure path
            service_state.mark_degraded("AI reporting policy unavailable", str(exc))
            _policy_cache = (now, AIReportingPolicy())
    return _policy_cache[1]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    service_state.mark_running()
    consume_task = asyncio.create_task(consume_loop())
    broadcast_task = asyncio.create_task(historian_broadcast_loop())
    try:
        yield
    finally:
        service_state.mark_stopped()
        consume_task.cancel()
        broadcast_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(consume_task, broadcast_task, return_exceptions=True)


app = FastAPI(title="Local Stream Engine AI Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    status = "starting"
    if service_state.running:
        status = "degraded" if service_state.degraded else "ok"
    return {
        "status": status,
        "provider": settings.llm_provider,
        "model": settings.llm_model_id,
        "base_url": settings.llm_endpoint_url,
        "last_error": service_state.last_error,
        "degraded": service_state.degraded,
        "degraded_reason": service_state.degraded_reason,
    }


@app.get("/telemetry")
async def telemetry() -> dict[str, Any]:
    return await _build_telemetry()

async def _build_telemetry() -> dict[str, Any]:
    return {
        "pipeline": [
            {"name": "ingest", "status": "active"},
            {"name": "process", "status": "active"},
            {"name": "ai", "status": "degraded" if service_state.degraded else "active" if service_state.running else "starting"},
            {"name": "observe", "status": "active"},
        ],
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model_id,
            "base_url": settings.llm_endpoint_url,
            "request_format": settings.llm_request_format,
            "last_error": service_state.last_error,
            "degraded": service_state.degraded,
            "degraded_reason": service_state.degraded_reason,
        },
    }

async def _broadcast_telemetry() -> None:
    payload = await _build_telemetry()
    dead: set[asyncio.Queue[dict[str, Any]]] = set()
    for queue in telemetry_subscribers:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(queue)
    for queue in dead:
        telemetry_subscribers.discard(queue)

@app.get("/events")
async def events() -> StreamingResponse:
    async def event_stream():
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=4)
        telemetry_subscribers.add(queue)
        try:
            yield f"data: {json.dumps(await _build_telemetry(), default=str)}\n\n"
            while service_state.running:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ":heartbeat\n\n"
        finally:
            telemetry_subscribers.discard(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


from services.historian.client import query_alarms, query_recent_events


# Historian SSE subscribers
historian_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
# Push trigger for the historian broadcast loop: set when new enriched data lands
# so the dashboard updates on change instead of on a fixed 2-second poll.
historian_refresh_event: asyncio.Event = asyncio.Event()

async def _broadcast_historian(payload: dict[str, Any]) -> None:
    dead: set[asyncio.Queue[dict[str, Any]]] = set()
    for queue in historian_subscribers:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(queue)
    for queue in dead:
        historian_subscribers.discard(queue)

@app.get("/historian/stream")
async def historian_stream() -> StreamingResponse:
    async def event_stream():
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        historian_subscribers.add(queue)
        try:
            # Send initial snapshot
            yield f"data: {json.dumps({'type': 'init', 'alarms': query_alarms(20), 'events': query_recent_events('industrial_events', 20)}, default=str)}\n\n"
            while service_state.running:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ":heartbeat\n\n"
        finally:
            historian_subscribers.discard(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )

async def historian_broadcast_loop() -> None:
    """Push historian updates to SSE/WS subscribers only when data changes.

    Runs alongside consume_loop in the lifespan so UI streams get live updates
    without polling. Uses content hashing to avoid broadcasting identical state.
    """
    last_snapshot = ""
    while service_state.running:
        try:
            alarms = query_alarms(50)
            events = query_recent_events("industrial_events", 50)
            snapshot = json.dumps({"alarms": alarms[:20], "events": events[:20]}, sort_keys=True, default=str)
            if snapshot != last_snapshot:
                last_snapshot = snapshot
                await _broadcast_historian(
                    {
                        "type": "update",
                        "alarms": alarms[:20],
                        "events": events[:20],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
        except Exception as exc:  # pragma: no cover - keep stream alive but surface errors
            service_state.mark_degraded("historian broadcast failure", str(exc))
            import logging
            logging.getLogger(__name__).warning("historian broadcast loop error: %s", exc)
        # Push-driven: wake immediately when new data is signalled, with a
        # bounded fallback so the snapshot still refreshes periodically even if
        # no signal arrives.
        try:
            await asyncio.wait_for(historian_refresh_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        historian_refresh_event.clear()


async def consume_loop() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_brokers,
            "group.id": "ai-gateway",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        }
    )
    producer = Producer({"bootstrap.servers": settings.kafka_brokers, "client.id": "ai-gateway"})
    consumer.subscribe([settings.processed_topic])

    report_queue: asyncio.Queue[ReportWorkItem | None] = asyncio.Queue(maxsize=max(1, settings.ai_report_queue_size))
    worker_tasks = [
        asyncio.create_task(report_worker(report_queue, producer, consumer))
        for _ in range(max(1, settings.ai_report_max_in_flight))
    ]

    batch: list[tuple[str, int, int, dict[str, Any]]] = []
    pending_offsets: dict[tuple[str, int], int] = {}
    anomaly_tracker = SustainedAnomalyTracker()
    deadline = time.monotonic() + reporting_policy().scheduled_interval_seconds

    try:
        while service_state.running:
            message = consumer.poll(0.25)
            if message and not message.error():
                consumed_events.inc()
                event = json.loads(message.value().decode("utf-8"))
                policy = reporting_policy()
                if policy.scheduled_enabled:
                    _append_bounded_evidence(
                        batch,
                        (message.topic(), message.partition(), message.offset(), event),
                        policy.max_evidence_events,
                    )
                    pending_offsets[(message.topic(), message.partition())] = message.offset() + 1
                else:
                    # A disabled scheduled policy must not retain normal events
                    # in memory while anomaly reporting remains independent.
                    batch.clear()
                    pending_offsets.clear()
                anomaly_evidence = anomaly_tracker.update(event, policy)
                if anomaly_evidence:
                    anomaly_batch = [(message.topic(), message.partition(), message.offset(), evidence) for evidence in anomaly_evidence]
                    try:
                        anomaly_job = create_report_job(
                            site_id=_batch_site(anomaly_evidence),
                            report_type="anomaly",
                            trigger_reason="sustained_anomaly",
                            window_start=None,
                            window_end=None,
                            policy=policy,
                            evidence=anomaly_evidence,
                        )
                    except Exception as exc:
                        service_state.mark_degraded("anomaly report failed", str(exc))
                    else:
                        await enqueue_report(
                            report_queue,
                            ReportWorkItem(
                                batch=anomaly_batch,
                                policy=policy,
                                job=anomaly_job,
                                offsets=[TopicPartition(message.topic(), message.partition(), message.offset() + 1)],
                            ),
                        )
                try:
                    low, high = consumer.get_watermark_offsets(TopicPartition(message.topic(), message.partition()), cached=True)
                    if high >= 0:
                        set_consumer_lag("ai_gateway", message.topic(), message.partition(), high - (message.offset() + 1))
                except Exception:
                    service_state.mark_degraded("consumer lag probe failed")

            policy = reporting_policy()
            # The legacy batch-size trigger is retained only as a compatibility
            # setting when no governed policy has been persisted yet. A durable
            # policy prevents accidental high-frequency LLM calls.
            ready_by_size = False
            ready_by_time = batch and time.monotonic() >= deadline
            if policy.scheduled_enabled and ready_by_time:
                job = None
                try:
                    payloads = [_batch_payload(item) for item in batch[: policy.max_evidence_events]]
                    job = create_report_job(
                        site_id=_batch_site(payloads),
                        report_type="scheduled",
                        trigger_reason="interval",
                        window_start=None,
                        window_end=None,
                        policy=policy,
                        evidence=payloads,
                    )
                except Exception as exc:
                    service_state.mark_degraded("AI report job could not be recorded", str(exc))
                await enqueue_report(
                    report_queue,
                    ReportWorkItem(
                        batch=batch[: policy.max_evidence_events],
                        policy=policy,
                        job=job,
                        offsets=[
                            TopicPartition(topic, partition, offset)
                            for (topic, partition), offset in pending_offsets.items()
                        ],
                    ),
                )
                batch = []
                pending_offsets = {}
                deadline = time.monotonic() + policy.scheduled_interval_seconds

            await asyncio.sleep(0)
    finally:
        for _ in worker_tasks:
            await report_queue.put(None)
        await asyncio.gather(*worker_tasks, return_exceptions=True)
        consumer.close()
        producer.flush(5)


async def enrich_batch(
    batch: list[tuple[str, int, int, dict[str, Any]]],
    producer: Producer,
    *,
    policy: AIReportingPolicy | None = None,
    job: dict[str, Any] | None = None,
) -> bool:
    batch_size_gauge.set(len(batch))
    payloads = [_batch_payload(item) for item in batch]
    for severity in ("normal", "warning", "critical"):
        count = sum(1 for event in payloads if event.get("severity") == severity)
        if count:
            batch_severity_total.labels(severity=severity).inc(count)
    prompt = build_industrial_prompt(payloads[: settings.llm_max_batch_size])

    started = time.monotonic()
    content: str | None = None
    used_fallback = False
    prompt_template = prompt_registry.get(DEFAULT_AI_PROMPT_TEMPLATE_ID)
    prompt_version = prompt_template.version if prompt_template is not None else "1.0.0"
    try:
        content = await llm_client.summarize(prompt, settings.llm_timeout_seconds)
        valid, errors, _payload = validate_industrial_summary(content)
        if not valid:
            fallback_reason = "; ".join(errors)
            if not settings.llm_allow_fallback:
                service_state.mark_degraded("llm output validation failed", f"LLM output validation failed: {fallback_reason}")
                asyncio.create_task(_broadcast_telemetry())
                return False
            content = build_fallback_summary(payloads, f"output_validation_failed: {fallback_reason}")
            service_state.mark_degraded("llm fallback active", f"LLM fallback active: output validation failed: {fallback_reason}")
            used_fallback = True
            asyncio.create_task(_broadcast_telemetry())
    except Exception as exc:
        if not settings.llm_allow_fallback:
            service_state.mark_degraded("llm request failed", str(exc))
            asyncio.create_task(_broadcast_telemetry())
            return False
        fallback_reason = f"{type(exc).__name__}: {exc}"
        content = build_fallback_summary(payloads, fallback_reason)
        service_state.mark_degraded("llm fallback active", f"LLM fallback active: {fallback_reason}")
        used_fallback = True
        asyncio.create_task(_broadcast_telemetry())
    finally:
        llm_latency.observe(time.monotonic() - started)

    if content is None:
        return False

    enriched_payload = build_ai_summary_event(
        payloads,
        summary=content,
        provider=settings.llm_provider,
        model_id=settings.llm_model_id,
        endpoint=settings.llm_endpoint_url,
        prompt_template_id=DEFAULT_AI_PROMPT_TEMPLATE_ID,
        prompt_version=prompt_version,
        used_fallback=used_fallback,
        latency_seconds=time.monotonic() - started,
        report_id=str(job["job_id"]) if job else None,
        report_type=str(job["report_type"]) if job else "scheduled",
        trigger_reason=str(job["trigger_reason"]) if job else "interval",
        policy_snapshot=policy.model_dump(mode="json") if policy else None,
    )
    producer.produce(settings.ai_enriched_topic, value=json.dumps(enriched_payload).encode("utf-8"))
    # Do not let the input consumer commit before the AI event has reached the
    # broker. This path is intentionally at-least-once; the historian sink is
    # idempotent and can safely retry after a process restart.
    flush = getattr(producer, "flush", None)
    if callable(flush):
        remaining = flush(max(1.0, settings.llm_timeout_seconds))
    else:
        # Small producer doubles used by unit tests and plugin adapters may
        # only expose poll(). The real confluent-kafka Producer always has
        # flush(), so this fallback is only a compatibility seam.
        producer.poll(0)
        remaining = 0
    if remaining:
        service_state.mark_degraded("AI event delivery pending", f"{remaining} Kafka event(s) not acknowledged")
        asyncio.create_task(_broadcast_telemetry())
        return False
    enriched_events.inc()
    last_success_epoch.set(time.time())
    if not used_fallback:
        service_state.mark_ok()
    asyncio.create_task(_broadcast_telemetry())
    # Signal the push-driven dashboard bus so subscribers refresh now instead of
    # waiting for the next fixed-interval poll.
    historian_refresh_event.set()
    return True


def _batch_payload(item: Any) -> dict[str, Any]:
    if isinstance(item, tuple) and len(item) == 4:
        return item[3]
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return dict(item)


def _batch_site(payloads: list[dict[str, Any]]) -> str:
    sites = sorted({str(event.get("site_id") or event.get("site") or "*") for event in payloads})
    return sites[0] if len(sites) == 1 else "*"

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

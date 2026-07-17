from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import datetime, timedelta, timezone
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
    provider_catalog,
)
from services.common.ai_event_contract import build_ai_summary_event, DEFAULT_AI_PROMPT_TEMPLATE_ID
from services.common.prompt_registry import prompt_registry
from services.common.service_health import ServiceHealthState
from services.common.runtime_metrics import set_consumer_lag
from services.common.ai_reporting import (
    AIReportingPolicy,
    SustainedAnomalyTracker,
    claim_next_report_job,
    complete_report_job,
    create_report_job,
    fail_report_job,
    get_policy,
    list_report_jobs,
)
from services.common.operational_briefing import (
    attach_briefing_memory,
    briefing_json_schema,
    build_briefing_context,
    build_briefing_prompt,
    deterministic_briefing,
    validate_briefing,
)


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
report_workers_active = Gauge("ai_gateway_report_workers_active", "AI report workers currently executing")
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


async def durable_job_worker(producer: Producer, worker_slot: int = 0) -> None:
    """Claim API-created and retryable reports from the durable job table."""
    from services.historian.client import query_report_evidence

    worker_id = f"ai-gateway-{id(producer)}-{worker_slot}"
    while service_state.running:
        try:
            job = await asyncio.to_thread(claim_next_report_job, worker_id)
        except Exception as exc:
            service_state.mark_degraded("AI report queue unavailable", str(exc))
            await asyncio.sleep(2)
            continue
        if job is None:
            await asyncio.sleep(1)
            continue
        try:
            report_workers_active.inc()
            policy = AIReportingPolicy.model_validate(job.get("policy_snapshot") or {})
            evidence = list(job.get("evidence") or [])
            if not evidence:
                evidence = await asyncio.to_thread(
                    query_report_evidence,
                    str(job.get("site_id") or "*"),
                    start=job.get("window_start"),
                    end=job.get("window_end"),
                    limit=policy.max_evidence_events,
                )
            batch = [(settings.processed_topic, 0, index, event) for index, event in enumerate(evidence)]
            result = await enrich_batch(batch, producer, policy=policy, job=job)
            if result:
                complete_report_job(str(job["job_id"]), result)
                report_jobs_completed.inc()
            else:
                fail_report_job(str(job["job_id"]), "AI output was not acknowledged")
                report_jobs_failed.inc()
        except Exception as exc:
            fail_report_job(str(job["job_id"]), str(exc))
            report_jobs_failed.inc()
        finally:
            report_workers_active.dec()


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


app = FastAPI(title="Ravan AI Gateway", version="0.1.0", lifespan=lifespan)


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
        "credential_configured": bool(settings.llm_api_key),
    }


@app.get("/providers")
async def providers() -> dict[str, Any]:
    """Expose provider choices without exposing credentials."""
    return {
        "providers": provider_catalog(),
        "configured_provider": settings.llm_provider,
        "configured_model": settings.llm_model_id,
        "credential_configured": bool(settings.llm_api_key),
        "local_only": bool(settings.llm_local_only),
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

    durable_workers = [
        asyncio.create_task(durable_job_worker(producer, worker_slot))
        for worker_slot in range(max(1, settings.ai_report_max_in_flight))
    ]

    batch: list[tuple[str, int, int, dict[str, Any]]] = []
    anomaly_tracker = SustainedAnomalyTracker()
    deadline = time.monotonic() + reporting_policy().scheduled_interval_seconds

    try:
        while service_state.running:
            message = consumer.poll(0.25)
            if message and not message.error():
                consumed_events.inc()
                event = json.loads(message.value().decode("utf-8"))
                policy = reporting_policy()
                if not policy.enabled:
                    batch.clear()
                    consumer.commit(
                        offsets=[TopicPartition(message.topic(), message.partition(), message.offset() + 1)],
                        asynchronous=False,
                    )
                    continue
                if policy.scheduled_enabled:
                    _append_bounded_evidence(
                        batch,
                        (message.topic(), message.partition(), message.offset(), event),
                        policy.max_evidence_events,
                    )
                else:
                    # A disabled scheduled policy must not retain normal events
                    # in memory while anomaly reporting remains independent.
                    batch.clear()
                anomaly_transition = anomaly_tracker.update_transition(event, policy)
                if anomaly_transition:
                    anomaly_evidence = list(anomaly_transition["evidence"])
                    transition_kind = str(anomaly_transition["kind"])
                    try:
                        anomaly_job = create_report_job(
                            site_id=_batch_site(anomaly_evidence),
                            report_type="recovery" if transition_kind == "recovery" else "anomaly",
                            trigger_reason="anomaly_recovered" if transition_kind == "recovery" else "sustained_anomaly",
                            window_start=None,
                            window_end=None,
                            policy=policy,
                            evidence=anomaly_evidence,
                        )
                    except Exception as exc:
                        service_state.mark_degraded("anomaly report failed", str(exc))
                try:
                    low, high = consumer.get_watermark_offsets(TopicPartition(message.topic(), message.partition()), cached=True)
                    if high >= 0:
                        set_consumer_lag("ai_gateway", message.topic(), message.partition(), high - (message.offset() + 1))
                except Exception:
                    service_state.mark_degraded("consumer lag probe failed")
                # Report evidence is bounded separately from Kafka delivery.
                # Never hold a stream offset for a 10-minute-to-one-day model
                # schedule; processed events remain queryable in the historian.
                consumer.commit(
                    offsets=[TopicPartition(message.topic(), message.partition(), message.offset() + 1)],
                    asynchronous=False,
                )

            policy = reporting_policy()
            # The legacy batch-size trigger is retained only as a compatibility
            # setting when no governed policy has been persisted yet. A durable
            # policy prevents accidental high-frequency LLM calls.
            ready_by_size = False
            ready_by_time = batch and time.monotonic() >= deadline
            if policy.scheduled_enabled and ready_by_time:
                jobs: list[dict[str, Any]] = []
                payloads_by_site: dict[str, list[dict[str, Any]]] = {}
                try:
                    payloads = [_batch_payload(item) for item in batch[: policy.max_evidence_events]]
                    window_end = datetime.now(timezone.utc)
                    for payload in payloads:
                        payloads_by_site.setdefault(_batch_site([payload]), []).append(payload)
                    for site_id, site_payloads in payloads_by_site.items():
                        jobs.append(
                            create_report_job(
                                site_id=site_id,
                                report_type="scheduled",
                                trigger_reason="interval",
                                window_start=window_end - timedelta(seconds=policy.scheduled_interval_seconds),
                                window_end=window_end,
                                policy=policy,
                                evidence=site_payloads,
                            )
                        )
                except Exception as exc:
                    service_state.mark_degraded("AI report job could not be recorded", str(exc))
                if jobs and len(jobs) == len(payloads_by_site):
                    batch = []
                    deadline = time.monotonic() + policy.scheduled_interval_seconds
                else:
                    # Retain the bounded evidence and retry job persistence
                    # without delaying Kafka consumption.
                    deadline = time.monotonic() + 5

            await asyncio.sleep(0)
    finally:
        for worker in durable_workers:
            worker.cancel()
        await asyncio.gather(*durable_workers, return_exceptions=True)
        consumer.close()
        producer.flush(5)


async def enrich_batch(
    batch: list[tuple[str, int, int, dict[str, Any]]],
    producer: Producer,
    *,
    policy: AIReportingPolicy | None = None,
    job: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    batch_size_gauge.set(len(batch))
    payloads = [_batch_payload(item) for item in batch]
    for severity in ("normal", "warning", "critical"):
        count = sum(1 for event in payloads if event.get("severity") == severity)
        if count:
            batch_severity_total.labels(severity=severity).inc(count)
    site_id = str(job.get("site_id") if job else _batch_site(payloads))
    previous_reports = list_report_jobs(
        site_id=None if site_id == "*" else site_id,
        status="completed",
        limit=settings.ai_report_memory_count,
    )
    context = build_briefing_context(
        payloads[: settings.llm_max_batch_size],
        report_type=str(job.get("report_type") if job else "scheduled"),
        site_id=site_id,
        previous_reports=previous_reports,
        max_events=policy.max_evidence_events if policy else settings.llm_max_batch_size,
        memory_hours=settings.ai_report_memory_hours,
    )
    prompt = build_briefing_prompt(context)

    started = time.monotonic()
    content: str | None = None
    used_fallback = False
    generation_metadata: dict[str, Any] = {}
    provider_response_received = False
    generation_error: str | None = None
    prompt_template = prompt_registry.get(DEFAULT_AI_PROMPT_TEMPLATE_ID)
    prompt_version = prompt_template.version if prompt_template is not None else "1.0.0"
    try:
        content, generation_metadata = await llm_client.summarize_structured(
            prompt,
            output_schema=briefing_json_schema(),
            timeout_seconds=settings.llm_timeout_seconds,
            cache_mode=settings.llm_prompt_cache_mode,
        )
        provider_response_received = True
        valid, errors, parsed_briefing = validate_briefing(content)
        if not valid:
            fallback_reason = "; ".join(errors)
            generation_error = f"output_validation_failed: {fallback_reason}"
            if not settings.llm_allow_fallback:
                service_state.mark_degraded("llm output validation failed", f"LLM output validation failed: {fallback_reason}")
                asyncio.create_task(_broadcast_telemetry())
                raise RuntimeError(f"LLM output validation failed: {fallback_reason}")
            parsed_briefing = deterministic_briefing(context, f"output_validation_failed: {fallback_reason}")
            content = json.dumps(parsed_briefing, separators=(",", ":"))
            service_state.mark_degraded("llm fallback active", f"LLM fallback active: output validation failed: {fallback_reason}")
            used_fallback = True
            asyncio.create_task(_broadcast_telemetry())
    except Exception as exc:
        if not settings.llm_allow_fallback:
            service_state.mark_degraded("llm request failed", str(exc))
            asyncio.create_task(_broadcast_telemetry())
            raise RuntimeError(f"LLM provider request failed: {exc}") from exc
        fallback_reason = f"{type(exc).__name__}: {exc}"
        generation_error = fallback_reason
        parsed_briefing = deterministic_briefing(context, fallback_reason)
        content = json.dumps(parsed_briefing, separators=(",", ":"))
        service_state.mark_degraded("llm fallback active", f"LLM fallback active: {fallback_reason}")
        used_fallback = True
        asyncio.create_task(_broadcast_telemetry())
    finally:
        llm_latency.observe(time.monotonic() - started)

    if content is None:
        return None

    valid, _errors, briefing = validate_briefing(content)
    if not valid or briefing is None:
        briefing = deterministic_briefing(context, "final_validation_failed")
        used_fallback = True
    else:
        briefing = attach_briefing_memory(briefing, context)

    generation_record = {
        **generation_metadata,
        "provider": settings.llm_provider,
        "model": settings.llm_model_id,
        "latency_seconds": time.monotonic() - started,
        "used_fallback": used_fallback,
        "prompt_template_id": DEFAULT_AI_PROMPT_TEMPLATE_ID,
        "prompt_version": prompt_version,
        "provider_response_received": provider_response_received,
        "generation_error": generation_error,
        "short_memory": context.get("short_memory", []),
        "short_memory_count": len(context.get("short_memory", [])),
        "kafka_acknowledged": True,
    }
    enriched_payload = build_ai_summary_event(
        payloads,
        summary=str(briefing.get("executive_summary") or briefing.get("headline") or ""),
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
        window_start=str(job.get("window_start")) if job and job.get("window_start") else None,
        window_end=str(job.get("window_end")) if job and job.get("window_end") else None,
        structured_report=briefing,
        generation_metadata=generation_record,
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
        raise RuntimeError(f"AI report was generated but {remaining} Kafka event(s) were not acknowledged")
    enriched_events.inc()
    last_success_epoch.set(time.time())
    if not used_fallback:
        service_state.mark_ok()
    asyncio.create_task(_broadcast_telemetry())
    # Signal the push-driven dashboard bus so subscribers refresh now instead of
    # waiting for the next fixed-interval poll.
    historian_refresh_event.set()
    return {
        "event_id": enriched_payload["event_id"],
        "briefing": briefing,
        "generation": generation_record,
        "evidence_event_ids": enriched_payload.get("source_event_ids", []),
    }


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

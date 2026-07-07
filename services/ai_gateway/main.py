from __future__ import annotations

import asyncio
import contextlib
import json
import time
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
service_state = ServiceHealthState(name="ai-gateway")
telemetry_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


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

    batch: list[tuple[str, int, int, dict[str, Any]]] = []
    deadline = time.monotonic() + settings.llm_batch_seconds

    try:
        while service_state.running:
            message = consumer.poll(0.25)
            if message and not message.error():
                consumed_events.inc()
                batch.append((message.topic(), message.partition(), message.offset(), json.loads(message.value().decode("utf-8"))))
                try:
                    low, high = consumer.get_watermark_offsets(TopicPartition(message.topic(), message.partition()), cached=True)
                    if high >= 0:
                        set_consumer_lag("ai_gateway", message.topic(), message.partition(), high - (message.offset() + 1))
                except Exception:
                    service_state.mark_degraded("consumer lag probe failed")

            ready_by_size = len(batch) >= settings.llm_max_batch_size
            ready_by_time = batch and time.monotonic() >= deadline
            if ready_by_size or ready_by_time:
                success = await enrich_batch(batch, producer)
                if success:
                    try:
                        consumer.commit(
                            offsets=[TopicPartition(topic, partition, offset + 1) for topic, partition, offset, _ in batch],
                            asynchronous=False,
                        )
                    except Exception as exc:
                        service_state.mark_degraded("offset commit failed", f"offset commit failed: {exc}")
                        asyncio.create_task(_broadcast_telemetry())
                batch = []
                deadline = time.monotonic() + settings.llm_batch_seconds

            await asyncio.sleep(0)
    finally:
        consumer.close()
        producer.flush(5)


async def enrich_batch(batch: list[tuple[str, int, int, dict[str, Any]]], producer: Producer) -> bool:
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
    )
    producer.produce(settings.ai_enriched_topic, value=json.dumps(enriched_payload).encode("utf-8"))
    producer.poll(0)
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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

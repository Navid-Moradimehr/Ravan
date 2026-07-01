from __future__ import annotations

import asyncio
import contextlib
import json
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Any

import httpx
from confluent_kafka import Consumer, Producer
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
from services.common.structured_output import validate_industrial_summary


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
service_state: dict[str, Any] = {"running": False, "last_error": None}
telemetry_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    service_state["running"] = True
    consume_task = asyncio.create_task(consume_loop())
    broadcast_task = asyncio.create_task(historian_broadcast_loop())
    try:
        yield
    finally:
        service_state["running"] = False
        consume_task.cancel()
        broadcast_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(consume_task, broadcast_task, return_exceptions=True)


app = FastAPI(title="Local Stream Engine AI Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if service_state["running"] else "starting",
        "provider": settings.llm_provider,
        "model": settings.llm_model_id,
        "base_url": settings.llm_endpoint_url,
        "last_error": service_state["last_error"],
    }


@app.get("/telemetry")
async def telemetry() -> dict[str, Any]:
    return await _build_telemetry()

async def _build_telemetry() -> dict[str, Any]:
    return {
        "pipeline": [
            {"name": "ingest", "status": "active"},
            {"name": "process", "status": "active"},
            {"name": "ai", "status": "active" if service_state["running"] else "starting"},
            {"name": "observe", "status": "active"},
        ],
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model_id,
            "base_url": settings.llm_endpoint_url,
            "request_format": settings.llm_request_format,
            "last_error": service_state["last_error"],
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
            yield f"data: {json.dumps(await _build_telemetry())}\n\n"
            while service_state["running"]:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(payload)}\n\n"
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


from pathlib import Path
from services.historian.client import query_recent_events, query_trend, query_alarms
from services.assets.model import load_hierarchy, hierarchy_to_tree
from services.scenarios.engine import list_scenarios

@app.get("/historian/events")
async def historian_events(table: str = "industrial_events", limit: int = 100) -> list[dict[str, Any]]:
    return query_recent_events(table, limit)


@app.get("/historian/trend")
async def historian_trend(asset_id: str, tag: str, hours: int = 1) -> list[dict[str, Any]]:
    return query_trend(asset_id, tag, hours)


@app.get("/historian/assets")
async def historian_assets() -> list[dict[str, Any]]:
    hierarchy = load_hierarchy(Path("config/assets.yaml"))
    return hierarchy_to_tree(hierarchy)


@app.get("/historian/scenarios")
async def historian_scenarios() -> list[dict[str, str]]:
    return list_scenarios()


@app.get("/historian/alarms")
async def historian_alarms(limit: int = 50) -> list[dict[str, Any]]:
    return query_alarms(limit)


replay_state: dict[str, Any] = {"running": False, "dataset": "", "scenario": "", "progress": 0, "events_emitted": 0}

@app.get("/historian/replay")
async def get_replay_status() -> dict[str, Any]:
    return replay_state

@app.post("/historian/replay")
async def start_replay(body: dict[str, Any]) -> dict[str, Any]:
    replay_state["running"] = True
    replay_state["dataset"] = body.get("dataset", "")
    replay_state["scenario"] = body.get("scenario", "")
    replay_state["progress"] = 0
    replay_state["events_emitted"] = 0
    return {"ok": True, "status": replay_state}

@app.delete("/historian/replay")
async def stop_replay() -> dict[str, Any]:
    replay_state["running"] = False
    replay_state["progress"] = 100
    return {"ok": True, "status": replay_state}


# Historian SSE subscribers
historian_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

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
            yield f"data: {json.dumps({'type': 'init', 'alarms': query_alarms(20), 'events': query_recent_events('industrial_events', 20)})}\n\n"
            while service_state["running"]:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(payload)}\n\n"
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
    while service_state["running"]:
        try:
            alarms = query_alarms(50)
            events = query_recent_events("industrial_events", 50)
            snapshot = json.dumps({"alarms": alarms[:20], "events": events[:20]}, sort_keys=True)
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
            import logging
            logging.getLogger(__name__).warning("historian broadcast loop error: %s", exc)
        await asyncio.sleep(2.0)


async def consume_loop() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.redpanda_brokers,
            "group.id": "ai-gateway",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
        }
    )
    producer = Producer({"bootstrap.servers": settings.redpanda_brokers, "client.id": "ai-gateway"})
    consumer.subscribe([settings.processed_topic])

    batch: list[dict[str, Any]] = []
    deadline = time.monotonic() + settings.llm_batch_seconds

    try:
        while service_state["running"]:
            message = consumer.poll(0.25)
            if message and not message.error():
                consumed_events.inc()
                batch.append(json.loads(message.value().decode("utf-8")))

            ready_by_size = len(batch) >= settings.llm_max_batch_size
            ready_by_time = batch and time.monotonic() >= deadline
            if ready_by_size or ready_by_time:
                await enrich_batch(batch, producer)
                batch = []
                deadline = time.monotonic() + settings.llm_batch_seconds

            await asyncio.sleep(0)
    finally:
        consumer.close()
        producer.flush(5)


async def enrich_batch(batch: list[dict[str, Any]], producer: Producer) -> None:
    batch_size_gauge.set(len(batch))
    for severity in ("normal", "warning", "critical"):
        count = sum(1 for event in batch if event.get("severity") == severity)
        if count:
            batch_severity_total.labels(severity=severity).inc(count)
    prompt = build_industrial_prompt(batch[: settings.llm_max_batch_size])

    started = time.monotonic()
    content: str | None = None
    try:
        content = await llm_client.summarize(prompt, settings.llm_timeout_seconds)
        valid, errors, _payload = validate_industrial_summary(content)
        if not valid:
            fallback_reason = "; ".join(errors)
            if not settings.llm_allow_fallback:
                service_state["last_error"] = f"LLM output validation failed: {fallback_reason}"
                asyncio.create_task(_broadcast_telemetry())
                return
            content = build_fallback_summary(batch, f"output_validation_failed: {fallback_reason}")
            service_state["last_error"] = f"LLM fallback active: output validation failed: {fallback_reason}"
            asyncio.create_task(_broadcast_telemetry())
    except Exception as exc:
        if not settings.llm_allow_fallback:
            service_state["last_error"] = str(exc)
            asyncio.create_task(_broadcast_telemetry())
            return
        fallback_reason = f"{type(exc).__name__}: {exc}"
        content = build_fallback_summary(batch, fallback_reason)
        service_state["last_error"] = f"LLM fallback active: {fallback_reason}"
        asyncio.create_task(_broadcast_telemetry())
    finally:
        llm_latency.observe(time.monotonic() - started)

    if content is None:
        return

    enriched_payload = {
        "source": "ai-gateway",
        "provider": settings.llm_provider,
        "model": settings.llm_model_id,
        "endpoint": settings.llm_endpoint_url,
        "batch_size": len(batch),
        "summary": content,
        "events": batch,
        "latency_seconds": round(time.monotonic() - started, 3),
    }
    producer.produce(settings.ai_enriched_topic, value=json.dumps(enriched_payload).encode("utf-8"))
    producer.poll(0)
    enriched_events.inc()
    last_success_epoch.set(time.time())
    asyncio.create_task(_broadcast_telemetry())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

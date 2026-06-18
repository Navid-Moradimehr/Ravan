from __future__ import annotations

import asyncio
import contextlib
import json
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
from confluent_kafka import Consumer, Producer
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response

from config import Settings


settings = Settings()
consumed_events = Counter("ai_gateway_consumed_events_total", "Processed events consumed by AI gateway")
enriched_events = Counter("ai_gateway_enriched_events_total", "AI enriched batches emitted")
llm_latency = Histogram("ai_gateway_llm_request_seconds", "LLM request latency in seconds")
batch_size_gauge = Gauge("ai_gateway_batch_size", "Most recent LLM batch size")
last_success_epoch = Gauge("ai_gateway_last_success_epoch", "Unix timestamp of last successful enrichment")
service_state: dict[str, Any] = {"running": False, "last_error": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    service_state["running"] = True
    task = asyncio.create_task(consume_loop())
    try:
        yield
    finally:
        service_state["running"] = False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Local Stream Engine AI Gateway", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if service_state["running"] else "starting",
        "model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "last_error": service_state["last_error"],
    }


@app.get("/telemetry")
async def telemetry() -> dict[str, Any]:
    return {
        "pipeline": [
            {"name": "ingest", "status": "active"},
            {"name": "process", "status": "active"},
            {"name": "ai", "status": "active" if service_state["running"] else "starting"},
            {"name": "observe", "status": "active"},
        ],
        "llm": {
            "model": settings.openai_model,
            "base_url": settings.openai_base_url,
            "last_error": service_state["last_error"],
        },
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    prompt = (
        "Summarize this processed industrial IoT batch. Identify critical devices, "
        "probable causes, and operator actions. Return concise JSON.\n\n"
        f"{json.dumps(batch[: settings.llm_max_batch_size], separators=(',', ':'))}"
    )

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": "You are an operations analyst for a streaming BI platform."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
    except Exception as exc:
        if not settings.llm_allow_fallback:
            service_state["last_error"] = str(exc)
            llm_latency.observe(time.monotonic() - started)
            return
        fallback_reason = f"{type(exc).__name__}: {exc}"
        content = build_fallback_summary(batch, fallback_reason)
        service_state["last_error"] = f"LLM fallback active: {fallback_reason}"
    finally:
        llm_latency.observe(time.monotonic() - started)

    enriched_payload = {
        "source": "ai-gateway",
        "model": settings.openai_model,
        "batch_size": len(batch),
        "summary": content,
        "events": batch,
        "latency_seconds": round(time.monotonic() - started, 3),
    }
    producer.produce(settings.ai_enriched_topic, value=json.dumps(enriched_payload).encode("utf-8"))
    producer.poll(0)
    enriched_events.inc()
    last_success_epoch.set(time.time())


def build_fallback_summary(batch: list[dict[str, Any]], error: str) -> str:
    critical = [event for event in batch if event.get("severity") == "critical"]
    warning = [event for event in batch if event.get("severity") == "warning"]
    devices = sorted({event.get("device_id", "unknown") for event in critical + warning})
    return json.dumps(
        {
            "mode": "deterministic_fallback",
            "reason": error,
            "batch_size": len(batch),
            "critical_count": len(critical),
            "warning_count": len(warning),
            "devices": devices[:10],
            "operator_action": "Inspect critical devices first; verify temperature, vibration, and pressure thresholds.",
        },
        separators=(",", ":"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

# Implementation Plan

## Product Direction

Build a local-first streaming and BI control plane that combines real-time ingestion, stream processing, operational dashboards, and AI explanations. The project takes the CGR/GITA Streaming and BI product references as functional inspiration, while prioritizing transparent local development, observable internals, and extensibility.

## MVP Sequence

1. Bootstrap repository, docs vault, scripts, and environment templates.
2. Start core Docker infrastructure: Redpanda, Redpanda Console, PostgreSQL, Prometheus, Grafana.
3. Produce deterministic IoT sensor events into Redpanda.
4. Process events with a PyFlink anomaly/window job.
5. Batch processed events into an OpenAI-compatible AI gateway.
6. Add Debezium CDC from PostgreSQL `orders`.
7. Add Grafana and web UI views for health, lag, throughput, CDC, and AI latency.

## Architecture Defaults

- Use PyFlink only for stream processing; defer ksqlDB.
- Use JSON for the first end-to-end slice; keep Schema Registry available for evolution.
- Keep LM Studio behind `OPENAI_BASE_URL` so local/cloud providers are interchangeable.
- Keep the LLM path asynchronous so ingestion and processing do not block on inference.

## Git Policy

Commit after each major vertical slice with conventional messages. Do not combine infrastructure, service logic, and UI in one large commit unless unavoidable.

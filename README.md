# Local Stream Engine

Local Stream Engine is a WSL2-first real-time data platform inspired by CGR/GITA Streaming and BI product capabilities: low-latency ingestion, stateful stream processing, operational analytics, and AI-assisted insight generation.

## Architecture

```text
Mock IoT Generator ─┐
                    ├─> Redpanda topics ─> PyFlink Processor ─> AI Gateway ─> enriched insights
PostgreSQL orders ─> Debezium CDC ───────┘

Prometheus scrapes services and exporters; Grafana and the web dashboard expose operational views.
```

## Stack

- Streaming: Redpanda, Redpanda Console, Schema Registry-compatible API
- Processing: Apache Flink / PyFlink
- CDC: PostgreSQL plus Debezium Kafka Connect
- AI: FastAPI service using OpenAI-compatible APIs, defaulting to LM Studio
- Observability: Prometheus and Grafana
- UI: Next.js, TypeScript, Tailwind CSS

## Quick Start

1. Copy `.env.example` to `.env` and adjust ports/model settings.
2. Start infrastructure: `docker compose -f docker/docker-compose.yml up -d`.
3. Create topics: `pwsh scripts/create-topics.ps1`.
4. Run the generator: `python services/ingestion/mock_generator.py`.
5. Run the AI gateway locally or through Docker Compose.

## Documentation

- `Guide.md` contains the original product brief.
- `ObsidianVault/` is the project knowledge base.
- `docs/` contains implementation-facing references and operational notes.

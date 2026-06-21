# Local Stream Engine

Local Stream Engine is a WSL2-first real-time data platform inspired by CGR/GITA Streaming and BI product capabilities: industrial edge ingestion, low-latency streaming, stateful processing, operational analytics, and AI-assisted insight generation.

## Architecture

```text
OPC UA Simulator -------+
MQTT Simulator ---------+--> Edge Ingest --> industrial.normalized --+
Modbus TCP Simulator ---+                                           |
                                                                    +--> Processor --> AI Gateway
Mock IoT Generator -------------------------------------------------+
PostgreSQL orders --> Debezium CDC --> Redpanda topics

Prometheus scrapes broker, edge, and AI metrics; Grafana and the web dashboard expose operational views.
```

## Stack

- Streaming: Redpanda, Redpanda Console, Schema Registry-compatible API
- Industrial edge: local OPC UA, MQTT, and Modbus TCP simulators plus normalized edge ingest
- Processing: Apache Flink / PyFlink plus the runtime Python processor
- CDC: PostgreSQL plus Debezium Kafka Connect
- AI: FastAPI service using OpenAI-compatible APIs, defaulting to LM Studio
- Observability: Prometheus and Grafana
- UI: Next.js, TypeScript, Tailwind CSS, shadcn/ui
- UI observability: live charts for throughput, AI latency, protocol mix, severity mix, and Grafana health

## Quick Start

1. Copy `.env.example` to `.env` and adjust ports/model settings.
2. Start infrastructure: `docker compose -f docker/docker-compose.yml up -d`.
3. Create topics: `powershell -ExecutionPolicy Bypass -File scripts/create-topics.ps1`.
4. Run the generator: `python services/ingestion/mock_generator.py`.
5. Run the AI gateway locally or through Docker Compose.
6. Start the dashboard locally: `cd ui; npm run dev`.
7. Open the dashboard: `http://localhost:3000`.

## Industrial Simulation

Run the hardware-free industrial pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-industrial-sim.ps1
```

Run a mixed-protocol soak:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/edge-soak.ps1 -Seconds 300 -MqttRatePerSecond 100
```

The edge path publishes raw protocol payloads to `industrial.raw`, validated envelopes to `industrial.normalized`, compatibility events to `iot.raw`, and invalid records to `industrial.dlq`.

## Documentation

- `Guide.md` contains the original product brief.
- `docs/app-functionality.md` explains the complete app behavior and feature map.
- `ObsidianVault/` is the project knowledge base.
- `docs/` contains implementation-facing references and operational notes.

## Useful URLs

- Dashboard: `http://localhost:3000`
- Edge metrics: `http://localhost:8090`
- Redpanda Console: `http://localhost:18080`
- Flink UI: `http://localhost:18088`
- AI Gateway: `http://localhost:8080/health`
- Grafana: `http://localhost:13000`
- Grafana login: `http://localhost:13000/login`
- Prometheus: `http://localhost:19090`

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

The ingest path now batches historian writes and the runtime processor and Flink
job share a single scoring module, which reduces duplicate logic and lowers
write amplification on the historian path.

## Stack

- Streaming: Redpanda, Redpanda Console, Schema Registry-compatible API
- Industrial edge: local OPC UA, MQTT, and Modbus TCP simulators plus normalized edge ingest
- Processing: Apache Flink / PyFlink plus the runtime Python processor
- Processing internals: shared scoring module used by both processing paths
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

## Control CLI

Install the package and get a browser-free operator surface:

```bash
pip install -e .
datastreamctl status
datastreamctl datasets --category synthetic
datastreamctl doctor
```

Or run without installing:

```bash
python -m services.cli.datastreamctl scenarios
```

### Runtime supervisor

Start, stop, and inspect the platform services without Docker-only orchestration:

```bash
datastreamd up --only api,ai --wait 12
datastreamd status
datastreamd logs api -n 50
datastreamd down
```

`datastreamd` manages Python services only; run `docker compose` first for Redpanda, Postgres/TimescaleDB, and Grafana.

See `docs/phase8-distribution.md` for the full distribution plan.

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
- `docs/app-functionality.md` explains the platform in plain language: what each part does, its inputs and outputs, and how users interact with it.
- `docs/feature-audit.md` lists the implemented feature set and current completion status.
- `docs/benchmark-results.md` records benchmark and test results.
- `docs/phase8-distribution.md` evaluates installable distribution options for the open-source release.
- `docs/testing-data-catalog.md` catalogs real, synthetic, and mock datasets that fit the platform.
- `data/benchmarks/industrial_mixed_benchmark.csv` is a local replay pack for mixed-protocol benchmark and stress cases.
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

# Ravan

Ravan is a self-hosted real-time data platform inspired by CGR/GITA Streaming and BI product capabilities: industrial edge ingestion, low-latency streaming, stateful processing, operational analytics, and AI-assisted insight generation.

## Architecture

```text
OPC UA Simulator -------+
MQTT Simulator ---------+--> Edge Ingest --> industrial.normalized --+
Modbus TCP Simulator ---+                                           |
                                                                    +--> Processor --> AI Gateway
Mock IoT Generator -------------------------------------------------+
PostgreSQL orders --> Debezium CDC --> Kafka topics

Prometheus scrapes edge and AI metrics; Grafana and the web dashboard expose operational views.
```

The ingest path now batches historian writes and the runtime processor and
distributed Flink job share the same enrichment contract, which reduces
duplicate logic and keeps severity output aligned across runtimes.

The API service is being split into domain routers with shared runtime helpers
so historian ingestion, asset views, and scenario endpoints are separated from
the remaining application surface without changing the public API.

## Stack

- Streaming: Apache Kafka, Kafka UI, internal schema registry contract
- Industrial edge: local OPC UA, MQTT, and Modbus TCP simulators plus normalized edge ingest
- Processing: Apache Flink / PyFlink plus the runtime Python processor fallback
- Processing internals: shared enrichment contract used by both processing paths
- CDC: PostgreSQL plus Debezium Kafka Connect
- AI: provider-neutral FastAPI gateway for OpenAI-compatible and open-weight model backends
- AI contracts: model registry, prompt registry, structured output validation, and read-only tool/context packages for future diagnostic agents
- Observability: Prometheus and Grafana
- UI: Next.js, TypeScript, Tailwind CSS, shadcn/ui
- UI observability: live charts for throughput, AI latency, protocol mix, severity mix, and Grafana health

The recommended production install is native on Windows Server / industrial PCs or Linux servers. WSL2 is useful for local development and demos, but it should not be a required production dependency or bundled as part of the installer unless the deployment target is explicitly a developer workstation.

Error handling is intentionally platform-neutral: the UI uses in-app banners, inline validation, route error boundaries, and dismissible toasts that work the same on Windows, Linux, and macOS packaged builds. No OS-specific notification API is required for the first release; native notifications can be added later behind an optional adapter if an installer shell needs them.

## Quick Start

1. Copy `.env.example` to `.env` and adjust ports/model settings.
2. Start infrastructure: `docker compose -f docker/docker-compose.yml up -d`.
   Start the API and dashboard profiles explicitly when using the UI:
   `docker compose --profile ui -f docker/docker-compose.yml up -d`. Add
   `--profile edge` for the hardware-free protocol simulators and edge ingest.
3. Topics are auto-created by the `kafka-init` service on first `up`. To create them manually (non-compose broker), run `powershell -ExecutionPolicy Bypass -File scripts/create-topics.ps1`.
4. Run the generator: `python services/ingestion/mock_generator.py`.
5. Run the AI gateway locally or through Docker Compose.
6. Start the dashboard locally: `cd ui; npm run dev`.
7. Open the dashboard: `http://localhost:3006`.

## Control CLI

Install the package and get a browser-free operator surface:

```bash
pip install -e .
datastreamctl status
datastreamctl datasets --category synthetic
datastreamctl doctor
datastreamctl preflight
datastreamctl update check --manifest-url https://github.com/OWNER/REPO/releases/latest/download/release-manifest.json
datastreamctl site-profile validate config/site-profiles/single-site.yaml
datastreamctl release-gate config/site-profiles/single-site.yaml --skip-network
```

Or run without installing:

```bash
python -m services.cli.datastreamctl scenarios
```

### Runtime supervisor

Start, stop, and inspect the platform services without Docker-only orchestration:

```bash
datastreamd up --only api,ai --wait 12 --site-profile config/site-profiles/single-site.yaml
datastreamd status
datastreamd logs api -n 50
datastreamd down
```

`datastreamd` manages the Python service surface only; run `docker compose` first for Kafka, Postgres/TimescaleDB, and Grafana. The distributed Flink processor is available through the compose `flink-job` service.

See `docs/phase8-distribution.md` for the full distribution plan.
See `docs/update-and-release-operations.md` for the opt-in release check and
the operator-controlled upgrade procedure.

## Industrial Simulation

Run the hardware-free industrial pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-industrial-sim.ps1
```

Run a mixed-protocol soak:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/edge-soak.ps1 -Seconds 300 -MqttRatePerSecond 100
powershell -ExecutionPolicy Bypass -File scripts/site-profile-soak.ps1 -SiteProfile config/site-profiles/single-site.yaml -Seconds 60 -MqttRatePerSecond 100 -RecoveryService processor
```

The edge path publishes raw protocol payloads to `industrial.raw`, validated envelopes to `industrial.normalized`, compatibility events to `iot.raw`, and invalid records to `industrial.dlq`.

When you want the distributed stream processor instead of the host-run Python fallback, start the Flink cluster services plus the `flink-job` compose service. The job uses keyed state, checkpointing, and the same runtime enrichment contract as the Python processor.

For Kubernetes validation, use `scripts/kind-rehearsal.ps1` together with
`docs/local-kubernetes-rehearsal.md` before moving to a real cluster.

Run the mixed replay benchmark pack:

```powershell
python scripts/benchmark_mixed_replay.py --events 100000 --batch-size 256
```

This replays `data/benchmarks/industrial_mixed_benchmark.csv` through the
validation, normalization, scoring, and serialization path used by the
industrial pipeline.

Run the AI gateway mock benchmark pack:

```powershell
python scripts/benchmark_ai_gateway_mock.py --provider openai_compat --events 100000 --batch-size 64
python scripts/benchmark_ai_gateway_mock.py --provider ollama --events 100000 --batch-size 64
```

This measures prompt construction, provider request shaping, and response parsing
against realistic industrial batches without depending on a live model server.

## Documentation

- `Guide.md` contains the original product brief.
- `docs/app-functionality.md` explains the platform in plain language: what each part does, its inputs and outputs, and how users interact with it.
- `docs/first-time-plc-ingest-guide.md` explains how a new user connects PLCs and sensors, how protocol differences are handled, and how multiple sources stay separate while still being correlatable.
- `docs/industrial-deployment-and-cli-architecture-note.md` summarizes the site-local vs central deployment model, dashboard expectations, and the CLI role.
- `docs/feature-audit.md` lists the implemented feature set and current completion status.
- `docs/phase8-distribution.md` evaluates installable distribution options for the open-source release.
- `docs/self-host-install-guide.md` gives the operator-facing local install and upgrade flow.
- `docs/release-packaging-checklist.md` maps installer contents to the actual repo structure.
- `docs/multi-site-rollout.md` defines the production-hardening plan for multi-site industrial deployment.
- `docs/model-agent-roadmap.md` defines the production model stack plan, including LLM roles, future agent infrastructure, and production gaps.
- `services/api_service/routers/modeling.py` exposes the read-only model, prompt, tool, and context contract surface.
- `services/api_service/routers/retrieval.py` exposes deterministic retrieval/search over historian, alarms, assets, reports, and scenarios.
- `config/site-profiles/` contains example site profile contracts for `single-site`, `plant-local`, and `federated` rollout shapes.
- `docs/testing-data-catalog.md` catalogs real, synthetic, and mock datasets that fit the platform.
- `docs/benchmark-results.md` includes the latest local benchmark numbers for the mixed replay path, repeat-run site matrix, and release-package verification.
- `services/api_service/routers/historian.py` and `services/api_service/runtime.py` hold the split historian routing and shared API runtime helpers.
- `scripts/benchmark_mixed_replay.py` runs the mixed replay benchmark against the local industrial replay pack.
- `scripts/benchmark_ai_gateway_mock.py` benchmarks the provider-neutral AI gateway against realistic mock industrial batches.
- `scripts/site-profile-soak.ps1` runs a live site-profile release gate and soak harness against the host-run runtime services.
- `data/benchmarks/industrial_mixed_benchmark.csv` is a local replay pack for mixed-protocol benchmark and stress cases.
- `ObsidianVault/` is the project knowledge base.
- `docs/deployment-payload-boundaries.md` defines installer, public-repository, and development-only file boundaries.
- `docs/` contains implementation-facing references and operational notes.

## Useful URLs

- Dashboard: `http://localhost:3006`
- Kafka UI: `http://localhost:18080`
- Edge metrics: `http://localhost:8090`
- Kafka UI: `http://localhost:18080`
- Flink UI: `http://localhost:18088`
- AI Gateway: `http://localhost:8080/health`
- Grafana: `http://localhost:13000`
- Grafana login: `http://localhost:13000/login`
- Prometheus: `http://localhost:19090`
## Industrial AI Data Foundation

The platform collects replayable industrial telemetry, semantic context, and
optional operational events. It can archive normalized events to TimescaleDB
and, when enabled, Apache Iceberg over MinIO or external S3-compatible storage.

For world-model data preparation, see:

- `docs/lakehouse-and-s3-guide.md`
- `docs/operational-event-guide.md`
- `docs/training-dataset-guide.md`
- `docs/jepa-training-guide.md`
- `docs/dreamer-training-guide.md`
- `docs/muzero-training-guide.md`

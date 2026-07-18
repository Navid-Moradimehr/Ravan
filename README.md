# Ravan

Ravan is a self-hosted real-time industrial data platform for edge ingestion, low-latency streaming, stateful processing, operational analytics, and AI-assisted insight generation.

## Architecture

```text
OPC UA, MQTT, Modbus, REST, and CDC sources --> Edge Ingest --> Kafka --> Flink --> Historian and AI

Prometheus scrapes edge and AI metrics; Grafana and the web dashboard expose operational views.
```

## Real-World Applications

Ravan can serve as the data foundation for manufacturing plants that collect
telemetry from production lines, PLCs, machine controllers, and sensor
gateways. Operators can normalize measurements, evaluate deterministic rules,
store historian data, track alarms, and expose the resulting streams to
dashboards, Grafana, AI services, or downstream systems.

Utilities and energy operators can use the same pipeline for substations,
power-generation equipment, renewable-energy assets, and distributed field
sites. Site-qualified events, Kafka topics, Flink processing, replayable
history, and optional object-storage sinks support local operation as well as
centralized analysis across multiple sites.

Water and wastewater facilities can connect treatment stages, pumps, tanks,
valves, and quality instruments through supported protocol adapters. The
platform can preserve raw and normalized events, route invalid records to the
DLQ, generate alarms from configured rules, and provide historical trend and
operational views.

Food, pharmaceutical, chemical, and mining operations can use Ravan for
condition monitoring, batch or process telemetry, environmental measurements,
equipment health, and maintenance-oriented analytics. Company-specific
topology, retention, security, credentials, MES/ERP integrations, and model
workflows remain operator-owned configuration rather than assumptions in the
platform core.

System integrators can deploy Ravan at individual sites, near edge networks, or
as a central data service receiving events from several site installations.
External lakehouse, object storage, BI, workflow, identity, and model-serving
systems can consume the platform's contracts when those capabilities are
required.

Teams preparing world-model or latent-space systems can use Ravan to collect
replayable telemetry together with asset relationships, topology, temporal
context, alarms, actions, and lineage. These datasets can be exported or
archived for user-owned JEPA-, Dreamer-, MuZero-, digital-twin, and simulation
training workflows without making a specific model architecture part of the
platform.

Teams building predictive-maintenance or tabular decision systems can use the
validated, normalized, and versioned dataset contracts as inputs for
user-owned gradient-boosting models such as XGBoost, LightGBM, and related
algorithms. Ravan provides the data and model-integration boundaries; feature
engineering, training, evaluation, and production serving remain selectable
by the deploying organization.

Ravan can also operate as the data backend for a customer-built website,
operator portal, or specialized industrial application. Those applications
can read historian and metadata through the API, subscribe to live streams
through WebSockets or Kafka, and use the platform's canonical event contracts
instead of implementing separate connector, buffering, normalization, and
historian pipelines. Ravan is not a general-purpose website host, so the
customer's frontend remains separately deployed and consumes these interfaces.

The ingest path now batches historian writes and the runtime processor and
distributed Flink job share the same enrichment contract, which reduces
duplicate logic and keeps severity output aligned across runtimes.

The API service is being split into domain routers with shared runtime helpers
so historian ingestion, asset views, and scenario endpoints are separated from
the remaining application surface without changing the public API.

## Stack

- Streaming: Apache Kafka, Kafka UI, internal schema registry contract
- Industrial edge: OPC UA, MQTT, and Modbus TCP connectors plus normalized edge ingest
- Processing: Apache Flink / PyFlink plus the runtime Python processor fallback
- Processing internals: shared enrichment contract used by both processing paths
- CDC: PostgreSQL plus Debezium Kafka Connect
- AI: provider-neutral FastAPI gateway with native Anthropic and Gemini adapters, OpenAI-compatible endpoints for OpenAI, DeepSeek, Qwen, Kimi, GLM, vLLM, LM Studio, and other compatible servers, plus Ollama and open-weight model support
- AI contracts: model registry, prompt registry, structured output validation, and read-only tool/context packages for future diagnostic agents
- AI data foundation: canonical replayable events, semantic asset relationships, temporal and operational context, lineage, versioned dataset manifests, and optional Iceberg/MinIO or S3-compatible archival for JEPA-, Dreamer-, and MuZero-style preparation
- Tabular ML integration: feature/label-ready dataset contracts and model-registry hooks for user-owned gradient-boosting models such as XGBoost; training and model serving remain selectable user integrations rather than hidden platform dependencies
- Observability: Prometheus and Grafana
- UI: Next.js, TypeScript, Tailwind CSS, shadcn/ui
- UI observability: live charts for throughput, AI latency, protocol mix, severity mix, and Grafana health

The recommended production install is native on Windows Server / industrial PCs or Linux servers. WSL2 is useful for local development and demos, but it should not be a required production dependency or bundled as part of the installer unless the deployment target is explicitly a developer workstation.

Error handling is intentionally platform-neutral: the UI uses in-app banners, inline validation, route error boundaries, and dismissible toasts that work the same on Windows, Linux, and macOS packaged builds. No OS-specific notification API is required for the first release; native notifications can be added later behind an optional adapter if an installer shell needs them.

## Quick Start

1. Copy `.env.example` to `.env` and adjust ports/model settings.
2. Start the production-shaped local stack: `./scripts/ravan.sh up -d` on Linux/macOS or `.\scripts\ravan.ps1 up -d` on Windows.
3. Topics are auto-created by the `kafka-init` service on first `up`. To create them manually (non-compose broker), run `powershell -ExecutionPolicy Bypass -File scripts/create-topics.ps1`.
4. Configure at least one real or externally managed source in `.env` or through the Source Connections page. The repository expects broker and device endpoints to be managed by the operator.
5. Open the dashboard: `http://localhost:3006`.

## How Installation Works

Ravan is installed in one of three practical ways:

1. Linux Site Server install for the full self-hosted runtime.
2. Docker Compose evaluation on Windows, Linux, or macOS.
3. Windows or macOS Operator shell for a dedicated desktop window that connects to an existing Site Server.

The normal user flow is:

1. Install the package that matches the deployment target.
2. Start the runtime or connect the operator shell to a running Site Server.
3. Open the dashboard and complete the first-time setup.
4. Add source connections for PLCs, sensors, or APIs.
5. Confirm data appears in Kafka UI, historian, Grafana, and the platform UI.
6. Add optional lakehouse, AI, reporting, or federated-site configuration only if the site needs it.

For a simple workstation evaluation, Docker Compose is the fastest path. For a production Linux deployment, use the Site Server installer. For Windows and macOS users, the Operator shell is the intended desktop entry point and should connect to a running Site Server rather than try to replace it.

## Control CLI

Source installs provide the Python CLI. Docker operators use `scripts/ravanctl`
and do not need host Python.

```powershell
.\scripts\ravanctl.ps1 doctor
.\scripts\ravanctl.ps1 status
```

Install the package and get a browser-free operator surface:

```bash
pip install -e .
ravanctl status
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

See `docs/self-host-install-guide.md` for deployment and
`docs/update-and-release-operations.md` for the opt-in release check and
operator-controlled upgrade procedure.

## Data Flow

The edge path publishes raw protocol payloads to `industrial.raw`, validated envelopes to `industrial.normalized`, compatibility events to `iot.raw`, and invalid records to `industrial.dlq`.

When you want the distributed stream processor instead of the host-run Python fallback, start the Flink cluster services plus the `flink-job` compose service. The job uses keyed state, checkpointing, and the same runtime enrichment contract as the Python processor.

For Kubernetes validation, use `scripts/kind-rehearsal.ps1` together with
`docs/local-kubernetes-rehearsal.md` before moving to a real cluster.

Run the mixed replay benchmark pack:

```powershell
python scripts/benchmark_mixed_replay.py --events 100000 --batch-size 256
```

This replays an operator-provided CSV through the validation, normalization,
scoring, and serialization path used by the industrial pipeline.

Run the AI gateway mock benchmark pack:

```powershell
python scripts/benchmark_ai_gateway_mock.py --provider openai_compat --events 100000 --batch-size 64
python scripts/benchmark_ai_gateway_mock.py --provider ollama --events 100000 --batch-size 64
```

This measures prompt construction, provider request shaping, and response parsing
against realistic industrial batches without depending on a live model server.

## Documentation

- `docs/app-functionality.md` explains the platform in plain language: what each part does, its inputs and outputs, and how users interact with it.
- `docs/first-time-plc-ingest-guide.md` explains how a new user connects PLCs and sensors, how protocol differences are handled, and how multiple sources stay separate while still being correlatable.
- `docs/deployment-targets.md` summarizes site-local, Compose, Kubernetes, and operator deployment models.
- `docs/latest-benchmark-results.md` reports the latest successful neutral Ravan benchmark measurements and their limitations.
- `docs/self-host-install-guide.md` gives the operator-facing local install and upgrade flow.
- `docs/release-content-policy.md` defines installer and public-repository content boundaries.
- `docs/multi-site-rollout.md` defines the production-hardening plan for multi-site industrial deployment.
- `docs/world-model-data-foundation.md` explains the model-data and future-agent infrastructure.
- `services/api_service/routers/modeling.py` exposes the read-only model, prompt, tool, and context contract surface.
- `services/api_service/routers/retrieval.py` exposes deterministic retrieval/search over historian, alarms, assets, reports, and scenarios.
- `config/site-profiles/` contains example site profile contracts for `single-site`, `plant-local`, and `federated` rollout shapes.
- `docs/deployment-targets.md` explains local validation and deployment boundaries.
- `services/api_service/routers/historian.py` and `services/api_service/runtime.py` hold the split historian routing and shared API runtime helpers.
- `scripts/benchmark_mixed_replay.py` runs the mixed replay benchmark against the local industrial replay pack.
- `scripts/benchmark_ai_gateway_mock.py` benchmarks the provider-neutral AI gateway against realistic mock industrial batches.
- `scripts/site-profile-soak.ps1` runs a live site-profile release gate and soak harness against the host-run runtime services.
- `docs/` contains curated user-facing operator references.

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
- `docs/world-model-data-foundation.md`
- `docs/jepa-training-guide.md`
- `docs/dreamer-training-guide.md`
- `docs/muzero-training-guide.md`

For tabular models such as gradient boosting or XGBoost, Ravan provides the
event, feature/label, dataset-manifest, lineage, replay, and model-registry
contracts needed to make training reproducible. The actual model training,
feature engineering choices, and serving runtime remain user-owned so a site
can use its preferred Python library, MLflow integration, GPU/CPU runtime, or
external model service.

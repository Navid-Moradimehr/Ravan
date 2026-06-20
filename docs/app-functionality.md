# App Functionality

## Product Purpose

Local Stream Engine is a local, hardware-free industrial streaming and BI platform. It demonstrates how plant telemetry can move from protocol-level acquisition into normalized event streams, anomaly scoring, AI-assisted summaries, dashboards, and observability.

The app is designed for realistic testing before connecting to physical PLCs, sensors, or plant networks.

## Main Capabilities

### Industrial Edge Ingestion

The edge tier simulates real industrial acquisition patterns:

- OPC UA simulator publishes deterministic pump tags.
- MQTT broker and simulator publish telemetry-style messages.
- Modbus TCP simulator exposes holding-register data.
- `edge-ingest` reads all three protocols and normalizes them into one event envelope.

The edge service publishes:

- `industrial.raw`: raw protocol-shaped input payloads.
- `industrial.normalized`: validated canonical industrial events.
- `industrial.dlq`: invalid or malformed records.
- `iot.raw`: compatibility records for the existing processor.

### Canonical Event Contract

Every normalized industrial event contains:

- `event_id`
- `source_protocol`
- `source_id`
- `asset_id`
- `tag`
- `value`
- `quality`
- `unit`
- `site`
- `line`
- `ts_source`
- `ts_ingest`
- `schema_version`

Malformed records are routed to `industrial.dlq` instead of crashing the service.

### Stream Processing

The runtime processor consumes `iot.raw` and emits `iot.processed`.

It adds:

- rolling window size
- average temperature
- average vibration
- anomaly score
- severity: `normal`, `warning`, or `critical`
- processing timestamp

### AI Gateway

The AI gateway consumes `iot.processed`, batches events, and sends summaries to an OpenAI-compatible API.

Default local target:

- Base URL: `http://172.17.0.1:1234/v1` or Docker host equivalent
- Chat model: `openai/gpt-oss-20B`
- Embedding model expected by the project: `text-embedding-nomic-embed-text-v1.5`

If LM Studio is unavailable or too slow, deterministic fallback summaries are emitted so the stream does not stall.

AI summaries are published to:

- `iot.ai_enriched`

### CDC Pipeline

PostgreSQL and Debezium provide a database-change stream.

The demo table is:

- `orders`

Debezium publishes changes to:

- `dbserver1.public.orders`

This validates the business-data side of a BI pipeline alongside machine telemetry.

### Dashboard

The Next.js dashboard provides:

- industrial command-center overview
- protocol source cards for OPC UA, MQTT, and Modbus TCP
- pipeline stage status
- sample event table
- test workflow commands
- AI gateway state
- operator links to Redpanda Console, Prometheus, Grafana, edge metrics, and AI health
- persisted light/dark theme toggle

### Observability

Prometheus scrapes:

- Redpanda metrics
- AI gateway metrics
- edge ingest metrics

Edge ingest exposes:

- validated event counters by protocol
- DLQ counters
- adapter error counters
- reconnect counters
- source-to-ingest latency histograms

Grafana is available for dashboards and trend analysis.

## Test Modes

### Unit Tests

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Validates envelope parsing, DLQ handling, compact serialization, and processor compatibility.

### Industrial Mock Workflow

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-industrial-sim.ps1
```

Starts Redpanda, protocol simulators, edge ingest, processor, AI gateway, Prometheus, and Grafana.

### Performance Soak

```powershell
powershell -ExecutionPolicy Bypass -File scripts/edge-soak.ps1 -Seconds 300 -MqttRatePerSecond 100
```

Runs a mixed-protocol load and reports edge counters.

### UI Validation

```powershell
npm --prefix ui run build
```

```powershell
$env:PLAYWRIGHT_CHROMIUM_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
npm --prefix ui run test:smoke
```

The smoke test validates dashboard rendering, operator links, test workflow tab, and theme switching.

## Production Boundary

The current system is suitable for local industrial workflow validation. It intentionally does not:

- auto-discover real PLCs
- control physical equipment
- connect to serial RTU Modbus
- manage plant-network certificates
- provide HA edge clustering

Those are production deployment concerns and should be added only when real hardware and network requirements are known.

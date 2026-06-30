# Testing Guide

## Feature Checklist

### Dashboard

- Open `http://localhost:3000`.
- Verify the industrial command-center title, KPI cards, protocol source cards, AI gateway panel, observability charts, and operator links render.
- Click `Light mode` and confirm the theme flips to a pale surface palette.
- Refresh the page and confirm the selected theme persists.
- Confirm the observability section shows throughput, AI latency, protocol mix, severity mix, and a Grafana status card.
- Confirm the Grafana operator link goes to `http://localhost:13000/login` rather than a public signup page.

### Industrial Edge Ingestion

- Run `powershell -ExecutionPolicy Bypass -File scripts/start-industrial-sim.ps1`.
- Open Redpanda Console and verify `industrial.raw`, `industrial.normalized`, `industrial.dlq`, and `iot.raw` exist.
- Confirm `industrial.normalized` receives OPC UA, MQTT, and Modbus records with `source_protocol`, `asset_id`, `tag`, `value`, `quality`, `ts_source`, and `ts_ingest`.
- Confirm `iot.raw` receives compatibility records that the existing processor can score.
- Open `http://localhost:8090` and verify edge Prometheus metrics are exposed.

### AI Gateway

- Open `http://localhost:8080/health`.
- Confirm `base_url` is `http://172.17.0.1:1234/v1`.
- Open `http://localhost:8080/telemetry`.
- Confirm the pipeline list appears and the last error is either empty or a fallback notice.
- Verify the gateway can be pointed at any OpenAI-compatible or open-weight backend by setting `LLM_PROVIDER`, `LLM_ENDPOINT_URL`, `LLM_MODEL_ID`, and `LLM_API_KEY`.
- For local-only deployments, set `LLM_LOCAL_ONLY=true` so the gateway refuses remote model endpoints.
- If you use a custom provider shape, set `LLM_REQUEST_PATH` and `LLM_REQUEST_FORMAT` explicitly.

### Streaming Ingestion

- Run `python services/ingestion/mock_generator.py`.
- Verify `iot.raw` receives messages in Redpanda Console.
- Stop and restart the generator to confirm the pipeline recovers cleanly.

### Stream Processing

- Confirm `iot.processed` receives records from the processor.
- Verify outlier events are marked with `severity=critical`.
- Restart the processor container and check that it resumes without manual repair.

### AI Enrichment

- Verify `iot.ai_enriched` receives summaries.
- If LM Studio is reachable, the gateway should call `openai/gpt-oss-20B`.
- If it is not reachable, deterministic fallback summaries should appear instead of stalling ingestion.

### CDC

- Run `powershell -ExecutionPolicy Bypass -File scripts/register-debezium.ps1`.
- Run `powershell -ExecutionPolicy Bypass -File scripts/seed-orders.ps1`.
- Confirm `dbserver1.public.orders` appears in Redpanda.

### Observability

- Open Grafana at `http://localhost:13000`.
- Open Prometheus at `http://localhost:19090`.
- Confirm metrics are visible for broker, edge ingest, AI gateway, and service health.
- Check the AI gateway exposes `ai_gateway_batch_size`, `ai_gateway_llm_request_seconds`, and `ai_gateway_batch_severity_total`.
- Confirm the dashboard still renders when Grafana or Prometheus is stopped; it should fall back to the built-in snapshot and show Grafana as offline.

## Performance Tests

1. Ingestion throughput: run the generator at `100`, `500`, and `1000` messages/sec and watch for lag growth.
2. Processor latency: measure the time from `iot.raw` to `iot.processed` using message timestamps.
3. AI latency: compare LM Studio against fallback mode and note p95 response time.
4. Restart recovery: stop one container at a time and verify offsets and topics recover cleanly.
5. UI responsiveness: keep the dashboard open while the generator runs and confirm the charts continue updating without layout shifts.
6. Industrial soak: run `scripts/edge-soak.ps1 -Seconds 300 -MqttRatePerSecond 100` and verify normalized throughput, DLQ count, severity mix, and service recovery.
7. Full-stack soak and restart: run `scripts/full-stack-soak.ps1 -Seconds 300 -MqttRatePerSecond 100 -RecoveryService processor` and verify the restarted service resumes without manual offset repair.
8. Grafana failure mode: stop Grafana and confirm the dashboard switches to offline state instead of sending you to an external signup page.
9. AI gateway mock benchmark: run `python scripts/benchmark_ai_gateway_mock.py --provider openai_compat --events 100000 --batch-size 64` and the same command with `--provider ollama`, then confirm the provider abstraction stays above 140K events/sec on the local mock transport.

## Industrial Readiness

The app includes a hardware-free edge adapter and simulators for OPC UA, MQTT, and Modbus TCP. This validates the same data acquisition pattern used in real deployments without requiring physical PLCs or sensors.

Real industrial systems typically use this shape:

- PLCs and sensors expose data through an edge layer using OPC UA, Modbus, or MQTT.
- A gateway or SCADA/IIoT runtime normalizes and forwards that data.
- Streaming infrastructure ingests the normalized events.
- Analytics, AI, dashboards, and historians consume the stream.

## Local Test Commands

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

```powershell
datastreamctl site-profile validate config/site-profiles/single-site.yaml
datastreamctl backup-drill --restore-db stream_engine_restore_demo
datastreamctl release-gate config/site-profiles/single-site.yaml --skip-network
```

```powershell
npm --prefix ui run build
```

```powershell
$env:PLAYWRIGHT_CHROMIUM_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
npm --prefix ui run test:smoke
```

## LM Studio Checks

```powershell
Invoke-RestMethod http://172.17.0.1:1234/v1/models
```

## Open-Weight Model Checks

The AI gateway also supports open-weight model servers that expose OpenAI-compatible APIs or their own HTTP shapes.

Examples:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

```powershell
$env:LLM_PROVIDER = "ollama"
$env:LLM_ENDPOINT_URL = "http://localhost:11434"
$env:LLM_MODEL_ID = "mistral"
$env:LLM_API_KEY = "unused"
Invoke-RestMethod http://localhost:8080/health
```

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://172.17.0.1:1234/v1/chat/completions `
  -Headers @{ Authorization = "Bearer lm-studio" } `
  -ContentType "application/json" `
  -Body (@{
    model = "openai/gpt-oss-20B"
    messages = @(@{ role = "user"; content = "Reply with OK only." })
    max_tokens = 20
  } | ConvertTo-Json -Depth 5)
```

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://172.17.0.1:1234/v1/embeddings `
  -Headers @{ Authorization = "Bearer lm-studio" } `
  -ContentType "application/json" `
  -Body (@{
    model = "text-embedding-nomic-embed-text-v1.5"
    input = "test embedding"
  } | ConvertTo-Json -Depth 5)
```

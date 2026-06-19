# Testing Guide

## Feature Checklist

### Dashboard

- Open `http://localhost:3000`.
- Verify the title, KPI cards, signal map, AI gateway panel, and operator links render.
- Click `Light mode` and confirm the theme flips to a pale surface palette.
- Refresh the page and confirm the selected theme persists.

### AI Gateway

- Open `http://localhost:8080/health`.
- Confirm `base_url` is `http://172.17.0.1:1234/v1`.
- Open `http://localhost:8080/telemetry`.
- Confirm the pipeline list appears and the last error is either empty or a fallback notice.

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
- Confirm metrics are visible for broker, AI gateway, and service health.

## Performance Tests

1. Ingestion throughput: run the generator at `100`, `500`, and `1000` messages/sec and watch for lag growth.
2. Processor latency: measure the time from `iot.raw` to `iot.processed` using message timestamps.
3. AI latency: compare LM Studio against fallback mode and note p95 response time.
4. Restart recovery: stop one container at a time and verify offsets and topics recover cleanly.
5. UI responsiveness: keep the dashboard open while the generator runs and confirm it stays interactive.

## Industrial Readiness

This app is not wired directly to PLCs or sensors. In real industrial systems, the typical pattern is:

- PLCs and sensors expose data through an edge layer using OPC UA, Modbus, or MQTT.
- A gateway or SCADA/IIoT runtime normalizes and forwards that data.
- Streaming infrastructure ingests the normalized events.
- Analytics, AI, dashboards, and historians consume the stream.

So the current app is suitable for industrial-style pipelines, but it needs an edge adapter before it can talk to a real plant network.

## Recommended Simulation Stack

- Use an OPC UA simulator or PLC simulator for tag-level testing.
- Use an MQTT broker/client simulator for telemetry-style testing.
- Keep the mock generator for load tests and failure injection.
- Add an edge bridge that converts OPC UA or MQTT messages into Redpanda topics.

## LM Studio Checks

```powershell
Invoke-RestMethod http://172.17.0.1:1234/v1/models
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

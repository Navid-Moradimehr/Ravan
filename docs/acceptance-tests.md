# Acceptance Tests

## Core Infrastructure

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-local.ps1
docker compose -f docker/docker-compose.yml ps
```

Expected result: Kafka, Kafka UI, PostgreSQL, AI Gateway, Prometheus, Grafana, and Dashboard are running.

## Ingestion

```powershell
python services/ingestion/mock_generator.py
```

Expected result: `iot.raw` receives approximately `MOCK_RATE_PER_SECOND` JSON messages per second.

## CDC

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register-debezium.ps1
powershell -ExecutionPolicy Bypass -File scripts/seed-orders.ps1
```

Expected result: Kafka UI shows `dbserver1.public.orders` messages for inserts and updates.

## AI Gateway

```powershell
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod http://localhost:8080/telemetry
```

Expected result: the service reports the configured provider and endpoint and no persistent error after events are processed.

Expected result: the service reports the configured provider, endpoint, and no persistent error after events are processed.

If the model server is not reachable, the gateway emits deterministic fallback summaries so the stream does not stall.

## Dashboard

```powershell
cd ui
npm run build
npm run start
```

Expected result: `http://localhost:3006` renders the command center and links to Kafka UI, Grafana, Prometheus, Flink, and AI health.

The dashboard Docker image is optional. Use `docker compose --profile ui -f docker/docker-compose.yml up -d dashboard` only after local npm install/build is healthy.

For browser smoke testing:

```powershell
$env:PLAYWRIGHT_CHROMIUM_PATH="$env:USERPROFILE\AppData\Local\ms-playwright\chromium-1200\chrome-win64\chrome.exe"
npm --prefix ui run test:smoke
```

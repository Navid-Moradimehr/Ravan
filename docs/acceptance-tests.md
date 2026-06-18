# Acceptance Tests

## Core Infrastructure

```powershell
pwsh scripts/run-local.ps1
docker compose -f docker/docker-compose.yml ps
```

Expected result: Redpanda, Console, PostgreSQL, AI Gateway, Prometheus, Grafana, and Dashboard are running.

## Ingestion

```powershell
python services/ingestion/mock_generator.py
```

Expected result: `iot.raw` receives approximately `MOCK_RATE_PER_SECOND` JSON messages per second.

## CDC

```powershell
pwsh scripts/register-debezium.ps1
pwsh scripts/seed-orders.ps1
```

Expected result: Redpanda Console shows `dbserver1.public.orders` messages for inserts and updates.

## AI Gateway

```powershell
Invoke-RestMethod http://localhost:8080/health
Invoke-RestMethod http://localhost:8080/telemetry
```

Expected result: the service reports the configured OpenAI-compatible endpoint and no persistent error after events are processed.

## Dashboard

```powershell
cd ui
npm run build
npm run start
```

Expected result: `http://localhost:3000` renders the operations cockpit and links to Redpanda Console, Grafana, Prometheus, Flink, and AI health.

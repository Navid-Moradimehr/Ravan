# Local Development Runbook

## Start

```powershell
Copy-Item .env.example .env
docker compose -f docker/docker-compose.yml up -d
powershell -ExecutionPolicy Bypass -File scripts/create-topics.ps1
```

## Verify

- Redpanda Console: `http://localhost:18080`
- Grafana: `http://localhost:13000`
- Prometheus: `http://localhost:19090`
- AI Gateway health: `http://localhost:8080/health`
- Dashboard: `http://localhost:3000`

## CDC

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register-debezium.ps1
powershell -ExecutionPolicy Bypass -File scripts/seed-orders.ps1
```

$ErrorActionPreference = "Stop"

docker compose -f docker/docker-compose.yml --profile demo --profile edge up -d kafka mqtt-broker mqtt-sim opcua-sim modbus-sim edge-ingest processor ai-gateway prometheus grafana
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
powershell -ExecutionPolicy Bypass -File scripts/create-industrial-topics.ps1

Write-Host "Industrial simulation is starting."
Write-Host "Kafka UI: http://localhost:18080"
Write-Host "Edge metrics: http://localhost:8090"
Write-Host "AI telemetry: http://localhost:8080/telemetry"

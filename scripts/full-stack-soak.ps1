param(
  [int]$Seconds = 300,
  [int]$MqttRatePerSecond = 100,
  [string]$RecoveryService = "processor",
  [switch]$IncludeApi
)

$ErrorActionPreference = "Stop"
$compose = "docker/docker-compose.yml"
$env:MQTT_RATE_PER_SECOND = "$MqttRatePerSecond"

$services = @(
  "kafka",
  "mqtt-broker",
  "mqtt-sim",
  "opcua-sim",
  "modbus-sim",
  "edge-ingest",
  "processor",
  "ai-gateway",
  "prometheus",
  "grafana"
)

$profiles = @("--profile", "edge")
if ($IncludeApi) {
  $profiles += @("--profile", "api")
  $services += @("timescaledb", "api-service")
}

Write-Host "Starting soak stack..."
docker compose -f $compose $profiles up -d $services
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

powershell -ExecutionPolicy Bypass -File scripts/create-industrial-topics.ps1

if ($IncludeApi) {
  Write-Host "API profile requested. If image pulls/builds fail, rerun after Docker registry access is healthy."
}

Write-Host "Waiting for metrics endpoints..."
Start-Sleep -Seconds 10

$started = Get-Date
$restartAt = [math]::Floor($Seconds / 2)
Write-Host "Running full-stack soak for $Seconds seconds at MQTT rate $MqttRatePerSecond msg/s."
Write-Host "Recovery event: restart '$RecoveryService' after $restartAt seconds."

if ($restartAt -gt 0) {
  Start-Sleep -Seconds $restartAt
  Write-Host "Restarting service '$RecoveryService'..."
  docker compose -f $compose restart $RecoveryService
  if ($LASTEXITCODE -ne 0) { throw "docker compose restart failed for $RecoveryService" }
  Start-Sleep -Seconds ($Seconds - $restartAt)
}
else {
  Start-Sleep -Seconds $Seconds
}

Write-Host ""
Write-Host "Edge counters after soak:"
$edgeMetrics = (Invoke-WebRequest -UseBasicParsing http://localhost:8090 -TimeoutSec 10).Content
$edgeMetrics -split "`n" | Where-Object {
  $_ -match "edge_ingest_events_total|edge_ingest_dlq_total|edge_ingest_adapter_errors_total|edge_ingest_reconnects_total"
} | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "AI gateway health after restart:"
try {
  $aiHealth = Invoke-RestMethod http://localhost:8080/health -TimeoutSec 10
  $aiHealth | ConvertTo-Json -Depth 4
}
catch {
  Write-Host "AI gateway health check failed: $($_.Exception.Message)"
}

if ($IncludeApi) {
  Write-Host ""
  Write-Host "API service health after restart:"
  try {
    $apiHealth = Invoke-RestMethod http://localhost:8020/health -TimeoutSec 10
    $apiHealth | ConvertTo-Json -Depth 4
  }
  catch {
    Write-Host "API service health check failed: $($_.Exception.Message)"
  }
}

$elapsed = ((Get-Date) - $started).TotalSeconds
Write-Host ""
Write-Host "Completed full-stack soak in $([math]::Round($elapsed, 1)) seconds."

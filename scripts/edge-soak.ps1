param(
  [int]$Seconds = 300,
  [int]$MqttRatePerSecond = 100
)

$ErrorActionPreference = "Stop"
$env:EDGE_PROTOCOLS = "mqtt,opcua,modbus"
$env:MQTT_RATE_PER_SECOND = "$MqttRatePerSecond"

docker compose -f docker/docker-compose.yml --profile demo --profile edge up -d kafka mqtt-broker mqtt-sim opcua-sim modbus-sim edge-ingest processor ai-gateway prometheus grafana
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
powershell -ExecutionPolicy Bypass -File scripts/create-industrial-topics.ps1

$started = Get-Date
Write-Host "Running mixed-protocol soak for $Seconds seconds at MQTT rate $MqttRatePerSecond msg/s."
Start-Sleep -Seconds $Seconds

Write-Host "Edge counters after soak:"
$metrics = (Invoke-WebRequest -UseBasicParsing http://localhost:8090 -TimeoutSec 10).Content
$metrics -split "`n" | Where-Object {
  $_ -match "edge_ingest_events_total|edge_ingest_dlq_total|edge_ingest_adapter_errors_total"
} | ForEach-Object { Write-Host $_ }

$elapsed = ((Get-Date) - $started).TotalSeconds
Write-Host "Completed edge soak in $([math]::Round($elapsed, 1)) seconds."

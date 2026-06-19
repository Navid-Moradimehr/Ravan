param(
  [int]$Seconds = 300,
  [int]$MqttRatePerSecond = 100
)

$ErrorActionPreference = "Stop"
$env:MQTT_RATE_PER_SECOND = "$MqttRatePerSecond"

docker compose -f docker/docker-compose.yml --profile edge up -d redpanda mqtt-broker mqtt-sim opcua-sim modbus-sim edge-ingest processor ai-gateway prometheus grafana
powershell -ExecutionPolicy Bypass -File scripts/create-industrial-topics.ps1

$started = Get-Date
Write-Host "Running mixed-protocol soak for $Seconds seconds at MQTT rate $MqttRatePerSecond msg/s."
Start-Sleep -Seconds $Seconds

Write-Host "Topic counts after soak:"
docker compose -f docker/docker-compose.yml exec -T redpanda rpk topic describe industrial.normalized --brokers redpanda:9092
docker compose -f docker/docker-compose.yml exec -T redpanda rpk topic describe industrial.dlq --brokers redpanda:9092

$elapsed = ((Get-Date) - $started).TotalSeconds
Write-Host "Completed edge soak in $([math]::Round($elapsed, 1)) seconds."

param(
  [string]$SiteProfile,
  [int]$Seconds = 60,
  [int]$MqttRatePerSecond = 100,
  [string]$RecoveryService = "processor"
)

$ErrorActionPreference = "Stop"

if (-not $SiteProfile) {
  throw "SiteProfile is required"
}

$python = ".\.venv\Scripts\python.exe"
$compose = "docker/docker-compose.yml"

function Get-MetricValue {
  param(
    [string]$MetricsText,
    [string]$MetricName
  )

  $line = ($MetricsText -split "`n" | Where-Object { $_ -match "^$MetricName(\{.*\})?\s+" } | Select-Object -Last 1)
  if (-not $line) {
    return 0.0
  }
  $parts = $line -split "\s+"
  return [double]$parts[-1]
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
        return $true
      }
    }
    catch {
    }
    Start-Sleep -Seconds 1
  }
  return $false
}

Write-Host "Preparing infrastructure for site profile soak..."
docker compose -f $compose --profile edge up -d kafka postgres mqtt-broker mqtt-sim opcua-sim modbus-sim prometheus grafana
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

Write-Host "Stopping compose-managed app services to avoid port conflicts..."
docker compose -f $compose stop ai-gateway edge-ingest processor api-service | Out-Null

powershell -ExecutionPolicy Bypass -File scripts/create-industrial-topics.ps1

& $python -m services.cli.datastreamd down | Out-Null

$env:MQTT_RATE_PER_SECOND = "$MqttRatePerSecond"
$env:TIMESCALE_HOST = "localhost"
$env:TIMESCALE_PORT = "15432"
$env:DATASTREAM_DOCKER_DB_SERVICE = "postgres"
$env:KAFKA_BROKERS = "localhost:19092"
$env:MQTT_HOST = "localhost"
$env:MQTT_PORT = "1883"
$env:OPCUA_ENDPOINT = "opc.tcp://localhost:14840/freeopcua/server/"
$env:MODBUS_HOST = "localhost"
$env:MODBUS_PORT = "15020"

Write-Host "Starting datastreamd services from site profile $SiteProfile..."
& $python -m services.cli.datastreamd up --site-profile $SiteProfile --only api,ai,edge,processor --wait 15
if ($LASTEXITCODE -ne 0) { throw "datastreamd up failed" }

if (-not (Wait-HttpOk -Url "http://localhost:8080/health" -TimeoutSeconds 30)) {
  throw "AI gateway did not become healthy"
}
if (-not (Wait-HttpOk -Url "http://localhost:8020/health" -TimeoutSeconds 30)) {
  throw "API service did not become healthy"
}

Write-Host "Running release gate..."
& $python -m services.cli.datastreamctl release-gate $SiteProfile
if ($LASTEXITCODE -ne 0) { throw "release gate failed" }

Start-Sleep -Seconds 10

$edgeBefore = (Invoke-WebRequest -UseBasicParsing http://localhost:8090 -TimeoutSec 10).Content
$eventsBefore = Get-MetricValue -MetricsText $edgeBefore -MetricName "edge_ingest_events_total"
$dlqBefore = Get-MetricValue -MetricsText $edgeBefore -MetricName "edge_ingest_dlq_total"
$errorsBefore = Get-MetricValue -MetricsText $edgeBefore -MetricName "edge_ingest_adapter_errors_total"

$started = Get-Date
$restartAt = [math]::Floor($Seconds / 2)
Write-Host "Running site-profile soak for $Seconds seconds at MQTT rate $MqttRatePerSecond msg/s."
Write-Host "Recovery event: restart '$RecoveryService' after $restartAt seconds."

if ($restartAt -gt 0) {
  Start-Sleep -Seconds $restartAt
  & $python -m services.cli.datastreamd restart $RecoveryService --site-profile $SiteProfile --wait 15
  if ($LASTEXITCODE -ne 0) { throw "datastreamd restart failed for $RecoveryService" }
  Start-Sleep -Seconds ($Seconds - $restartAt)
}
else {
  Start-Sleep -Seconds $Seconds
}

$edgeAfter = (Invoke-WebRequest -UseBasicParsing http://localhost:8090 -TimeoutSec 10).Content
$eventsAfter = Get-MetricValue -MetricsText $edgeAfter -MetricName "edge_ingest_events_total"
$dlqAfter = Get-MetricValue -MetricsText $edgeAfter -MetricName "edge_ingest_dlq_total"
$errorsAfter = Get-MetricValue -MetricsText $edgeAfter -MetricName "edge_ingest_adapter_errors_total"
$elapsed = ((Get-Date) - $started).TotalSeconds

$eventsDelta = $eventsAfter - $eventsBefore
$dlqDelta = $dlqAfter - $dlqBefore
$errorsDelta = $errorsAfter - $errorsBefore
$eventsPerSecond = if ($elapsed -gt 0) { $eventsDelta / $elapsed } else { 0 }

$aiHealth = Invoke-RestMethod http://localhost:8080/health -TimeoutSec 10
$apiHealth = Invoke-RestMethod http://localhost:8020/health -TimeoutSec 10

Write-Host ""
Write-Host "Site profile soak results"
Write-Host "profile=$SiteProfile"
Write-Host ("elapsed_seconds={0:N1}" -f $elapsed)
Write-Host ("events_delta={0:N0}" -f $eventsDelta)
Write-Host ("events_per_second={0:N2}" -f $eventsPerSecond)
Write-Host ("dlq_delta={0:N0}" -f $dlqDelta)
Write-Host ("adapter_errors_delta={0:N0}" -f $errorsDelta)
Write-Host ("ai_status={0}" -f $aiHealth.status)
Write-Host ("api_status={0}" -f $apiHealth.status)
Write-Host ("ai_provider={0}" -f $aiHealth.provider)
Write-Host ("ai_model={0}" -f $aiHealth.model)

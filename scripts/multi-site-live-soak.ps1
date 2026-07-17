param(
  [int]$Seconds = 900,
  [int]$Sites = 3,
  [int]$RatePerSecond = 100,
  [int]$DeviceCount = 50,
  [string]$Topic = "industrial.normalized",
  [string]$KafkaBrokers = "",
  [string]$ComposeProject = "",
  [string]$ComposeEnvFile = "",
  [string]$ComposeFile = "docker/docker-compose.yml"
)

$ErrorActionPreference = "Stop"

if ($Sites -lt 2) {
  throw "Sites must be at least 2 for a multisite soak"
}

$python = "py -3.13"
$root = (Resolve-Path ".").Path
$logRoot = Join-Path $root ".datastream\logs\multi-site-live-soak"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$runId = "multi-{0}" -f ([guid]::NewGuid().ToString("N").Substring(0, 12))
$composeProjectValue = if ($ComposeProject) { $ComposeProject } elseif ($env:RAVAN_COMPOSE_PROJECT) { $env:RAVAN_COMPOSE_PROJECT } else { "local-stream-engine" }
$composeEnvFileValue = if ($ComposeEnvFile) { $ComposeEnvFile } elseif ($env:RAVAN_COMPOSE_ENV_FILE) { $env:RAVAN_COMPOSE_ENV_FILE } else { "" }
if ($composeEnvFileValue -and (Test-Path -LiteralPath $composeEnvFileValue)) {
  foreach ($line in Get-Content -LiteralPath $composeEnvFileValue) {
    if ($line -match '^\s*([^#=][^=]*)=(.*)$') {
      [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
  }
}
$kafkaBrokersValue = if ($KafkaBrokers) { $KafkaBrokers } elseif ($env:KAFKA_BROKERS) { $env:KAFKA_BROKERS } else { "localhost:19092" }
$env:KAFKA_BROKERS = $kafkaBrokersValue

function Get-HostPort {
  param(
    [string]$Name,
    [int]$Default
  )

  $value = [Environment]::GetEnvironmentVariable($Name)
  if ($value) {
    return [int]$value
  }
  return $Default
}

$processorPort = Get-HostPort -Name "PROCESSOR_HOST_PORT" -Default 8094
$fanoutPort = Get-HostPort -Name "FANOUT_HOST_PORT" -Default 18095
$processedFanoutPort = Get-HostPort -Name "PROCESSED_FANOUT_HOST_PORT" -Default 18097
$aiFanoutPort = Get-HostPort -Name "AI_FANOUT_HOST_PORT" -Default 18096
$apiPort = Get-HostPort -Name "API_SERVICE_HOST_PORT" -Default 8020
$aiGatewayPort = Get-HostPort -Name "AI_GATEWAY_HOST_PORT" -Default 8080
$flinkPort = Get-HostPort -Name "FLINK_JOBMANAGER_HOST_PORT" -Default 8081
$kafkaUiPort = Get-HostPort -Name "KAFKA_UI_HOST_PORT" -Default 18080
$grafanaPort = Get-HostPort -Name "GRAFANA_PROXY_HOST_PORT" -Default 3000

function Invoke-Compose {
  param([string[]]$Arguments)

  $composeArgs = @("-p", $composeProjectValue)
  if ($composeEnvFileValue) {
    $composeArgs += @("--env-file", $composeEnvFileValue)
  }
  $composeArgs += @("-f", $ComposeFile)
  $composeArgs += $Arguments
  & docker compose @composeArgs
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose failed with exit code $LASTEXITCODE"
  }
}

function Start-Generator {
  param(
    [string]$SiteId,
    [int]$Rate
  )

  $stdout = Join-Path $logRoot "$SiteId.out.log"
  $stderr = Join-Path $logRoot "$SiteId.err.log"
  $env:MOCK_SITE_ID = $SiteId
  $env:MOCK_RATE_PER_SECOND = "$Rate"
  $env:MOCK_DEVICE_COUNT = "$DeviceCount"
  $env:MOCK_MAX_EVENTS = "0"
  $env:MOCK_DURATION_SECONDS = "$Seconds"
  $env:IOT_TOPIC = $Topic
  $reportPath = Join-Path $logRoot "$SiteId.report.json"
  $launcher = @"
`$env:KAFKA_BROKERS = '$kafkaBrokersValue'
`$env:MOCK_SITE_ID = '$SiteId'
`$env:MOCK_RATE_PER_SECOND = '$Rate'
`$env:MOCK_DEVICE_COUNT = '$DeviceCount'
`$env:MOCK_MAX_EVENTS = '0'
`$env:MOCK_DURATION_SECONDS = '$Seconds'
`$env:IOT_TOPIC = '$Topic'
`$env:MOCK_REPORT_PATH = '$reportPath'
py -3.13 -m services.ingestion.mock_generator
"@
  Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-Command", $launcher
  ) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
}

Write-Host "Starting multisite live soak..."
Write-Host "seconds=$Seconds sites=$Sites rate_per_second=$RatePerSecond device_count=$DeviceCount topic=$Topic"
Write-Host "compose_project=$composeProjectValue compose_file=$ComposeFile"
Write-Host "kafka_brokers=$kafkaBrokersValue"
Write-Host "ports=processor:$processorPort fanout:$fanoutPort processed_fanout:$processedFanoutPort ai_fanout:$aiFanoutPort api:$apiPort ai_gateway:$aiGatewayPort flink:$flinkPort kafka_ui:$kafkaUiPort grafana:$grafanaPort"

Write-Host "Stopping baseline compose source simulators so the soak is isolated..."
Invoke-Compose -Arguments @("stop", "mqtt-sim", "opcua-sim", "modbus-sim", "edge-ingest") | Out-Null

  $processes = @()
  for ($index = 1; $index -le $Sites; $index++) {
    $siteId = "$runId-site-$index"
    $siteRate = [math]::Max(1, $RatePerSecond)
    $processes += Start-Generator -SiteId $siteId -Rate $siteRate
  }

Start-Sleep -Seconds ($Seconds + 15)

foreach ($process in $processes) {
  if (!$process.HasExited) {
    Wait-Process -Id $process.Id -Timeout 30 -ErrorAction SilentlyContinue
  }
  if (!$process.HasExited) {
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
  }
  Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 5

function Get-MetricValue {
  param(
    [string]$MetricsText,
    [string]$MetricName
  )

  $line = ($MetricsText -split "`n" | Where-Object { $_ -match "^$MetricName(\{.*\})?\s+" } | Select-Object -Last 1)
  if (-not $line) {
    return $null
  }
  $parts = $line -split "\s+"
  return [double]$parts[-1]
}

Write-Host ""
Write-Host "Multisite live soak results"
Write-Host "----------------------------------------"
Write-Host ("processes_started={0}" -f $processes.Count)
Write-Host ("run_id={0}" -f $runId)

for ($index = 1; $index -le $Sites; $index++) {
  $siteId = "$runId-site-$index"
  $reportPath = Join-Path $logRoot "$siteId.report.json"
  if (Test-Path $reportPath) {
    $generatorReport = Get-Content $reportPath -Raw | ConvertFrom-Json
    Write-Host ("{0}_attempted={1}" -f $siteId, $generatorReport.attempted)
    Write-Host ("{0}_acknowledged={1}" -f $siteId, $generatorReport.acknowledged)
    Write-Host ("{0}_failed={1}" -f $siteId, $generatorReport.failed)
    Write-Host ("{0}_queue_full={1}" -f $siteId, $generatorReport.queue_full)
    Write-Host ("{0}_effective_attempt_rate={1}" -f $siteId, $generatorReport.effective_attempt_rate)
    Write-Host ("{0}_effective_ack_rate={1}" -f $siteId, $generatorReport.effective_ack_rate)
  }
  else {
    Write-Host ("{0}_generator_report=missing" -f $siteId)
  }
}

try {
  $processorMetrics = $null
  try {
    $processorMetrics = (Invoke-WebRequest -UseBasicParsing "http://localhost:$processorPort/metrics" -TimeoutSec 10).Content
  }
  catch {
    Write-Host "processor_metrics=unavailable"
  }

  function Get-OptionalContent([string]$Url) {
    try { return (Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 5).Content } catch { return $null }
  }
  function Get-OptionalJson([string]$Url) {
    try { return Invoke-RestMethod $Url -TimeoutSec 5 } catch { return $null }
  }
  function Get-EndpointProbe([string]$Url) {
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    try {
      Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 5 | Out-Null
      $timer.Stop()
      return [math]::Round($timer.Elapsed.TotalMilliseconds, 2)
    }
    catch {
      $timer.Stop()
      return $null
    }
  }
  $fanoutMetrics = Get-OptionalContent "http://localhost:$fanoutPort"
  $processedFanoutMetrics = Get-OptionalContent "http://localhost:$processedFanoutPort"
  $aiFanoutMetrics = Get-OptionalContent "http://localhost:$aiFanoutPort"
  $apiHealth = Get-OptionalJson "http://localhost:$apiPort/health"
  $aiHealth = Get-OptionalJson "http://localhost:$aiGatewayPort/health"
  $flinkJobs = Get-OptionalJson "http://localhost:$flinkPort/jobs/overview"
  $kafkaUiLatency = Get-EndpointProbe "http://localhost:$kafkaUiPort"
  $grafanaLatency = Get-EndpointProbe "http://localhost:$grafanaPort"

  if ($processorMetrics) {
    Write-Host ("processor_consumer_lag={0}" -f (Get-MetricValue -MetricsText $processorMetrics -MetricName "datastream_broker_consumer_lag_messages"))
  }
  Write-Host ("fanout_consumer_lag={0}" -f $(if ($fanoutMetrics) { Get-MetricValue -MetricsText $fanoutMetrics -MetricName "datastream_broker_consumer_lag_messages" } else { "unavailable" }))
  Write-Host ("processed_fanout_consumer_lag={0}" -f $(if ($processedFanoutMetrics) { Get-MetricValue -MetricsText $processedFanoutMetrics -MetricName "datastream_broker_consumer_lag_messages" } else { "unavailable" }))
  Write-Host ("ai_fanout_consumer_lag={0}" -f $(if ($aiFanoutMetrics) { Get-MetricValue -MetricsText $aiFanoutMetrics -MetricName "datastream_broker_consumer_lag_messages" } else { "unavailable" }))
  Write-Host ("api_status={0}" -f $(if ($apiHealth) { $apiHealth.status } else { "unavailable" }))
  Write-Host ("ai_status={0}" -f $(if ($aiHealth) { $aiHealth.status } else { "unavailable" }))
  Write-Host ("ai_provider={0}" -f $(if ($aiHealth) { $aiHealth.provider } else { "unavailable" }))
  Write-Host ("ai_model={0}" -f $(if ($aiHealth) { $aiHealth.model } else { "unavailable" }))
  Write-Host ("flink_running_jobs={0}" -f $(if ($flinkJobs) { @($flinkJobs.jobs | Where-Object { $_.state -eq "RUNNING" }).Count } else { "unavailable" }))
  Write-Host ("kafka_ui_probe_ms={0}" -f $(if ($null -ne $kafkaUiLatency) { $kafkaUiLatency } else { "unavailable" }))
  Write-Host ("grafana_probe_ms={0}" -f $(if ($null -ne $grafanaLatency) { $grafanaLatency } else { "unavailable" }))
}
catch {
  Write-Host "Could not collect all runtime counters: $($_.Exception.Message)"
}

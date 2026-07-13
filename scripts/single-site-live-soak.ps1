param(
  [int]$Seconds = 900,
  [int]$RatePerSecond = 100,
  [int]$DeviceCount = 50,
  [string]$Topic = "industrial.normalized"
)

$ErrorActionPreference = "Stop"

$python = "py -3.13"
$root = (Resolve-Path ".").Path
$logRoot = Join-Path $root ".datastream\logs\single-site-live-soak"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$runId = "single-{0}" -f ([guid]::NewGuid().ToString("N").Substring(0, 12))

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
  $env:MOCK_REPORT_PATH = (Join-Path $logRoot "$SiteId.report.json")

  Start-Process -WindowStyle Hidden -FilePath "py" -ArgumentList @(
    "-3.13",
    "-m",
    "services.ingestion.mock_generator"
  ) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
}

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

Write-Host "Starting single-site live soak..."
Write-Host "seconds=$Seconds rate_per_second=$RatePerSecond device_count=$DeviceCount topic=$Topic"

Write-Host "Stopping baseline compose source simulators so the soak is isolated..."
docker compose -f docker/docker-compose.yml stop mqtt-sim opcua-sim modbus-sim edge-ingest | Out-Null

$process = Start-Generator -SiteId "site-01" -Rate $RatePerSecond

Start-Sleep -Seconds ($Seconds + 2)
if (!$process.HasExited) {
  Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
}
Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Single-site live soak results"
Write-Host "----------------------------------------"
Write-Host ("processes_started={0}" -f 1)

$reportPath = Join-Path $logRoot "site-01.report.json"
if (Test-Path $reportPath) {
  $generatorReport = Get-Content $reportPath -Raw | ConvertFrom-Json
  Write-Host ("run_id={0}" -f $runId)
  Write-Host ("generator_attempted={0}" -f $generatorReport.attempted)
  Write-Host ("generator_acknowledged={0}" -f $generatorReport.acknowledged)
  Write-Host ("generator_failed={0}" -f $generatorReport.failed)
  Write-Host ("generator_queue_full={0}" -f $generatorReport.queue_full)
  Write-Host ("generator_effective_attempt_rate={0}" -f $generatorReport.effective_attempt_rate)
  Write-Host ("generator_effective_ack_rate={0}" -f $generatorReport.effective_ack_rate)
}
else {
  Write-Host "generator_report=missing"
}

try {
  $processorMetrics = $null
  try {
    $processorMetrics = (Invoke-WebRequest -UseBasicParsing http://localhost:8094/metrics -TimeoutSec 10).Content
  }
  catch {
    Write-Host "processor_metrics=unavailable"
  }

  $fanoutMetrics = (Invoke-WebRequest -UseBasicParsing http://localhost:18095 -TimeoutSec 10).Content
  $processedFanoutMetrics = (Invoke-WebRequest -UseBasicParsing http://localhost:18097 -TimeoutSec 10).Content
  $aiFanoutMetrics = (Invoke-WebRequest -UseBasicParsing http://localhost:18096 -TimeoutSec 10).Content
  $apiHealth = Invoke-RestMethod http://localhost:8020/health -TimeoutSec 10
  $aiHealth = Invoke-RestMethod http://localhost:8080/health -TimeoutSec 10

  if ($processorMetrics) {
    Write-Host ("processor_consumer_lag={0}" -f (Get-MetricValue -MetricsText $processorMetrics -MetricName "datastream_broker_consumer_lag_messages"))
  }
  Write-Host ("fanout_consumer_lag={0}" -f (Get-MetricValue -MetricsText $fanoutMetrics -MetricName "datastream_broker_consumer_lag_messages"))
  Write-Host ("processed_fanout_consumer_lag={0}" -f (Get-MetricValue -MetricsText $processedFanoutMetrics -MetricName "datastream_broker_consumer_lag_messages"))
  Write-Host ("ai_fanout_consumer_lag={0}" -f (Get-MetricValue -MetricsText $aiFanoutMetrics -MetricName "datastream_broker_consumer_lag_messages"))
  Write-Host ("api_status={0}" -f $apiHealth.status)
  Write-Host ("ai_status={0}" -f $aiHealth.status)
  Write-Host ("ai_provider={0}" -f $aiHealth.provider)
  Write-Host ("ai_model={0}" -f $aiHealth.model)
}
catch {
  Write-Host "Could not collect all runtime counters: $($_.Exception.Message)"
}

param(
  [int]$Seconds = 900,
  [int]$Sites = 3,
  [int]$RatePerSecond = 100,
  [int]$DeviceCount = 50,
  [string]$Topic = "industrial.normalized"
)

$ErrorActionPreference = "Stop"

if ($Sites -lt 2) {
  throw "Sites must be at least 2 for a multisite soak"
}

$python = "py -3.13"
$root = (Resolve-Path ".").Path
$logRoot = Join-Path $root ".datastream\logs\multi-site-live-soak"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

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
  $env:IOT_TOPIC = $Topic
  Start-Process -WindowStyle Hidden -FilePath "py" -ArgumentList @(
    "-3.13",
    "-m",
    "services.ingestion.mock_generator"
  ) -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
}

Write-Host "Starting multisite live soak..."
Write-Host "seconds=$Seconds sites=$Sites rate_per_second=$RatePerSecond device_count=$DeviceCount topic=$Topic"

Write-Host "Stopping baseline compose source simulators so the soak is isolated..."
docker compose -f docker/docker-compose.yml stop mqtt-sim opcua-sim modbus-sim edge-ingest | Out-Null

  $processes = @()
  for ($index = 1; $index -le $Sites; $index++) {
    $siteId = ("site-{0:00}" -f $index)
    $siteRate = [math]::Max(1, $RatePerSecond)
    $processes += Start-Generator -SiteId $siteId -Rate $siteRate
  }

Start-Sleep -Seconds $Seconds

foreach ($process in $processes) {
  try {
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
  }
  catch {
  }
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

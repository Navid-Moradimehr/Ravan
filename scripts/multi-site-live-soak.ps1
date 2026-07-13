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
$runId = "multi-{0}" -f ([guid]::NewGuid().ToString("N").Substring(0, 12))

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

Write-Host "Starting multisite live soak..."
Write-Host "seconds=$Seconds sites=$Sites rate_per_second=$RatePerSecond device_count=$DeviceCount topic=$Topic"

Write-Host "Stopping baseline compose source simulators so the soak is isolated..."
docker compose -f docker/docker-compose.yml stop mqtt-sim opcua-sim modbus-sim edge-ingest | Out-Null

  $processes = @()
  for ($index = 1; $index -le $Sites; $index++) {
    $siteId = "$runId-site-$index"
    $siteRate = [math]::Max(1, $RatePerSecond)
    $processes += Start-Generator -SiteId $siteId -Rate $siteRate
  }

Start-Sleep -Seconds ($Seconds + 2)

foreach ($process in $processes) {
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
    $processorMetrics = (Invoke-WebRequest -UseBasicParsing http://localhost:8094/metrics -TimeoutSec 10).Content
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
  $fanoutMetrics = Get-OptionalContent "http://localhost:18095"
  $processedFanoutMetrics = Get-OptionalContent "http://localhost:18097"
  $aiFanoutMetrics = Get-OptionalContent "http://localhost:18096"
  $apiHealth = Get-OptionalJson "http://localhost:8020/health"
  $aiHealth = Get-OptionalJson "http://localhost:8080/health"

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
}
catch {
  Write-Host "Could not collect all runtime counters: $($_.Exception.Message)"
}

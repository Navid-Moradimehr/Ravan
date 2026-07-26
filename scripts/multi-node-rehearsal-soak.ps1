param(
  [int]$Seconds = 900,
  [int]$Sites = 3,
  [int]$RatePerSecond = 20,
  [int]$DeviceCount = 10,
  [string]$ComposeFile = "docker/docker-compose.yml",
  [string]$HelmProfile = "k8s/helm/profiles/multi-node-values.yaml",
  [string]$ReportPath = ".datastream/reports/multi-node-rehearsal-soak.json"
)

$ErrorActionPreference = "Stop"
if ($Seconds -lt 900) { throw "This rehearsal must run for at least 900 seconds." }
if ($Sites -lt 2) { throw "Sites must be at least 2." }

$root = (Resolve-Path ".").Path
$reportFile = Join-Path $root $ReportPath
New-Item -ItemType Directory -Force -Path (Split-Path $reportFile -Parent) | Out-Null

function Invoke-Checked {
  param([string]$File, [string[]]$Arguments)
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE" }
}

Write-Host "Rendering multi-node Helm profile..."
$rendered = & helm template ravan k8s/helm -f $HelmProfile
if ($LASTEXITCODE -ne 0) { throw "Helm profile rendering failed" }
$renderText = $rendered -join "`n"
$profileChecks = [ordered]@{
  api_replicas = [bool]($renderText -match "replicas: 3")
  ai_replicas = [bool]($renderText -match "replicas: 2")
  shared_assistant_store = [bool]($renderText -match 'RAVAN_ASSISTANT_STORE_BACKEND: "postgres"')
  readiness_probes = [bool]($renderText -match "readinessProbe:")
  disruption_budgets = [bool]($renderText -match "kind: PodDisruptionBudget")
  flink_operator_contract = [bool]($renderText -match 'FLINK_OPERATOR_ENABLED: "true"')
}

Write-Host "Checking live Docker dependencies..."
$composePs = docker compose -f $ComposeFile ps --format json | ConvertFrom-Json
$required = @("kafka", "timescaledb", "api-service", "ai-gateway", "processor", "fanout", "processed-fanout", "ai-fanout", "flink-job", "prometheus", "grafana", "kafka-ui")
$runtimeChecks = [ordered]@{}
foreach ($service in $required) {
  $container = @($composePs | Where-Object { $_.Service -eq $service } | Select-Object -First 1)
  $runtimeChecks[$service] = [bool]($container -and ($container.State -eq "running"))
}

$runId = "multi-node-{0}" -f ([guid]::NewGuid().ToString("N").Substring(0, 12))
$logPath = Join-Path $root ".datastream/logs/$runId.log"
Write-Host "Starting $Seconds-second live multi-site campaign. run_id=$runId"
$arguments = @(
  "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "scripts/multi-site-live-soak.ps1"),
  "-Seconds", "$Seconds", "-Sites", "$Sites", "-RatePerSecond", "$RatePerSecond", "-DeviceCount", "$DeviceCount",
  "-ComposeFile", $ComposeFile
)
$startedAt = [DateTime]::UtcNow
& powershell.exe @arguments 2>&1 | Tee-Object -FilePath $logPath
$exitCode = $LASTEXITCODE
$finishedAt = [DateTime]::UtcNow

$result = [ordered]@{
  scenario = "multi-node-rehearsal-soak"
  run_id = $runId
  duration_seconds = $Seconds
  sites = $Sites
  rate_per_second_per_site = $RatePerSecond
  devices_per_site = $DeviceCount
  started_at = $startedAt.ToString("o")
  finished_at = $finishedAt.ToString("o")
  helm_profile = $HelmProfile
  profile_checks = $profileChecks
  runtime_checks_at_start = $runtimeChecks
  docker_execution_mode = "single-node-compose"
  live_campaign_exit_code = $exitCode
  log_path = $logPath
  interpretation = "The live campaign validates the full local event path. Helm checks validate multi-node intent; they do not certify a Kubernetes cluster."
}
$result | ConvertTo-Json -Depth 6 | Set-Content -Path $reportFile -Encoding utf8
Write-Host "Report written to $reportFile"
if ($exitCode -ne 0) { exit $exitCode }

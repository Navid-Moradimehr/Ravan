[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ComposeFile,
    [string]$CurrentCompose = $(if ($env:RAVAN_COMPOSE_FILE) { $env:RAVAN_COMPOSE_FILE } else { "docker/docker-compose.yml" }),
    [string]$UpgradeDir = $(if ($env:RAVAN_UPGRADE_DIR) { $env:RAVAN_UPGRADE_DIR } else { ".datastream/upgrades" }),
    [int]$TimeoutSeconds = $(if ($env:RAVAN_UPGRADE_TIMEOUT) { [int]$env:RAVAN_UPGRADE_TIMEOUT } else { 120 })
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker Engine is required" }
if (-not (Test-Path $ComposeFile)) { throw "New Compose file not found: $ComposeFile" }
if (-not (Test-Path $CurrentCompose)) { throw "Current Compose file not found: $CurrentCompose" }

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$runDir = Join-Path $UpgradeDir $stamp
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$backupCompose = Join-Path $runDir "previous-compose.yml"
docker compose -f $CurrentCompose config | Out-File -FilePath $backupCompose -Encoding utf8
docker compose -f $ComposeFile config --quiet
docker compose -f $CurrentCompose ps | Out-File -FilePath (Join-Path $runDir "previous-status.txt") -Encoding utf8

Write-Host "Stopping current Ravan services without removing volumes..."
docker compose -f $CurrentCompose stop
docker compose -f $ComposeFile --profile ui --profile edge up -d
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    $api = docker compose -f $ComposeFile ps api-service --status running --format "{{.Name}}"
    if ($LASTEXITCODE -eq 0 -and $api) {
        Write-Host "Upgrade started successfully. Rollback file: $backupCompose"
        exit 0
    }
    Start-Sleep -Seconds 3
}

Write-Warning "Upgrade failed; restoring the previous Compose configuration."
docker compose -f $ComposeFile stop
docker compose -f $backupCompose up -d
throw "Upgrade failed; rollback started from $backupCompose"

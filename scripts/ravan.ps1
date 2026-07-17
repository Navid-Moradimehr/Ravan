[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop (or Docker Engine) is required. Install and start Docker, then retry."
}

# Production starts Ravan UI and edge ingestion, but never demo protocol simulators.
$composeFile = if ($env:RAVAN_COMPOSE_FILE) { $env:RAVAN_COMPOSE_FILE } else { "docker/docker-compose.yml" }
docker compose -f $composeFile --profile ui --profile edge @Arguments
exit $LASTEXITCODE

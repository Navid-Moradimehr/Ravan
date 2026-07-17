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
docker compose -f docker/docker-compose.yml --profile ui --profile edge @Arguments
exit $LASTEXITCODE

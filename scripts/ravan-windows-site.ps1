[CmdletBinding()]
param(
    [ValidateSet("start", "stop", "restart", "status", "open")]
    [string]$Action = "start",
    [string]$ComposeFile = "docker/docker-compose.yml",
    [string]$ProjectName = "ravan",
    [switch]$Build
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop is required. Install it, start it, and run this command again."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but its engine is not ready. Start Docker Desktop and retry."
}

$composeArgs = @(
    "compose", "--project-name", $ProjectName, "-f", $ComposeFile,
    "--profile", "ui", "--profile", "edge"
)

switch ($Action) {
    "start" {
        if ($Build) {
            docker @composeArgs build
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        docker @composeArgs up -d
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        Write-Host "Ravan Site Server is starting at http://localhost:3006"
        Write-Host "Use the Source Connections page to configure operator-managed sources."
    }
    "stop" { docker @composeArgs stop }
    "restart" { docker @composeArgs restart }
    "status" { docker @composeArgs ps }
    "open" { Start-Process "http://localhost:3006" }
}

exit $LASTEXITCODE

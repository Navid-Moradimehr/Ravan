$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item .env.example .env
}

docker compose -f docker/docker-compose.yml up -d
powershell -ExecutionPolicy Bypass -File scripts/create-topics.ps1
Write-Host "Core services started. Configure a source through the Source Connections page."

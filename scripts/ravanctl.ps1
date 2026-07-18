[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$compose = if ($env:RAVAN_COMPOSE_FILE) { $env:RAVAN_COMPOSE_FILE } else { "docker/docker-compose.yml" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop (or Docker Engine) is required. Install and start Docker, then retry."
}

docker compose -f $compose ps api-service --status running --format "{{.Name}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "The Ravan API service is not running. Start the stack first: .\\scripts\\ravan.ps1 up"
}

# The operator CLI executes in the API container, so Docker deployments do not
# require Python or Python package installation on the operator workstation.
# Preflight is special: it needs the checkout and operator .env, but those
# should not be copied into the long-running API container.
if ($Arguments.Count -gt 0 -and $Arguments[0] -eq "preflight") {
    $root = (Get-Location).Path
    $extraArgs = @()
    if ($Arguments.Count -gt 1) {
        $extraArgs = $Arguments[1..($Arguments.Count - 1)]
    }
    $composeInWorkspace = $compose.Replace('\\', '/')
    $preflightArgs = @("preflight", "--compose-file", "/workspace/$composeInWorkspace", "--site-profile", "/workspace/config/site-profiles/single-site.yaml", "--project-manifest", "/workspace/config/project-manifest.yaml") + $extraArgs
    if (Test-Path ".env") {
        $preflightArgs += @("--env-file", "/workspace/.env")
    }
    docker compose -f $compose run --rm --no-deps -T -v "${root}:/workspace:ro" -w /workspace api-service python -m services.cli.datastreamctl @preflightArgs
} else {
    docker compose -f $compose exec -T api-service python -m services.cli.datastreamctl @Arguments
}
exit $LASTEXITCODE

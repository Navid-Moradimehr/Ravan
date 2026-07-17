[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$compose = "docker/docker-compose.yml"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop (or Docker Engine) is required. Install and start Docker, then retry."
}

docker compose -f $compose ps api-service --status running --format "{{.Name}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "The Ravan API service is not running. Start the stack first: .\\scripts\\ravan.ps1 up"
}

# The operator CLI executes in the API container, so Docker deployments do not
# require Python or Python package installation on the operator workstation.
docker compose -f $compose exec -T api-service python -m services.cli.datastreamctl @Arguments
exit $LASTEXITCODE

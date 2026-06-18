$ErrorActionPreference = "Stop"

$connectUrl = $env:CONNECT_URL
if (-not $connectUrl) {
    $connectUrl = "http://localhost:18083"
}

$body = Get-Content -Raw -LiteralPath "services/ingestion/debezium-postgres-orders.json"
Invoke-RestMethod -Method Put -Uri "$connectUrl/connectors/postgres-orders-cdc/config" -ContentType "application/json" -Body $body
Write-Host "Registered Debezium connector postgres-orders-cdc"

$ErrorActionPreference = "Stop"

$compose = "docker/docker-compose.yml"
$topics = @(
  "industrial.raw",
  "industrial.normalized",
  "industrial.dlq",
  "iot.raw",
  "iot.processed",
  "iot.ai_enriched"
)

foreach ($topic in $topics) {
  docker compose -f $compose exec -T redpanda rpk topic create $topic --brokers redpanda:9092 --partitions 3 --replicas 1 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Topic may already exist: $topic"
  } else {
    Write-Host "Created topic: $topic"
  }
}

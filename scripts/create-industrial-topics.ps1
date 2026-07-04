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
  docker compose -f $compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists --topic $topic --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Topic may already exist: $topic"
  } else {
    Write-Host "Created topic: $topic"
  }
}

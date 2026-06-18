$ErrorActionPreference = "Stop"

$broker = $env:REDPANDA_BROKERS
if (-not $broker) {
    $broker = "localhost:19092"
}

$topics = @(
    @{ Name = "iot.raw"; Partitions = 3 },
    @{ Name = "iot.processed"; Partitions = 3 },
    @{ Name = "iot.ai_enriched"; Partitions = 1 },
    @{ Name = "connect_configs"; Partitions = 1 },
    @{ Name = "connect_offsets"; Partitions = 1 },
    @{ Name = "connect_statuses"; Partitions = 1 }
)

foreach ($topic in $topics) {
    docker compose -f docker/docker-compose.yml exec -T redpanda rpk topic create $topic.Name --brokers redpanda:9092 --partitions $topic.Partitions --replicas 1 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Topic exists or create failed: $($topic.Name)"
    } else {
        Write-Host "Created topic: $($topic.Name)"
    }
}

$ErrorActionPreference = "Stop"

$broker = $env:KAFKA_BROKERS
if (-not $broker) {
    $broker = "localhost:19092"
}

$topics = @(
    @{ Name = "industrial.raw"; Partitions = 3; Compact = $false },
    @{ Name = "industrial.normalized"; Partitions = 3; Compact = $false },
    @{ Name = "industrial.dlq"; Partitions = 3; Compact = $false },
    @{ Name = "iot.raw"; Partitions = 3; Compact = $false },
    @{ Name = "iot.processed"; Partitions = 3; Compact = $false },
    @{ Name = "iot.ai_enriched"; Partitions = 3; Compact = $false },
    @{ Name = "platform.metadata.threshold-policies"; Partitions = 3; Compact = $true },
    @{ Name = "connect_configs"; Partitions = 1; Compact = $true },
    @{ Name = "connect_offsets"; Partitions = 1; Compact = $true },
    @{ Name = "connect_statuses"; Partitions = 1; Compact = $true }
)

foreach ($topic in $topics) {
    docker compose -f docker/docker-compose.yml exec -T kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists --topic $topic.Name --bootstrap-server localhost:9092 --partitions $topic.Partitions --replication-factor 1 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Topic exists or create failed: $($topic.Name)"
    } else {
        Write-Host "Created topic: $($topic.Name)"
    }

    if ($topic.Compact) {
        docker compose -f docker/docker-compose.yml exec -T kafka /opt/kafka/bin/kafka-configs.sh --alter --bootstrap-server localhost:9092 --entity-type topics --entity-name $topic.Name --add-config cleanup.policy=compact
        Write-Host "Configured compact cleanup policy: $($topic.Name)"
    }
}

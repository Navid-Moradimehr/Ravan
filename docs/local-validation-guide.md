# Local Full-Stack Validation

Ravan includes a repeatable industrial-soak runner for validating the local
Docker deployment without physical PLCs or sensors. It uses the bundled OPC
UA, MQTT, and Modbus simulators and follows the same canonical event path as a
real deployment: source connector, edge ingest, Kafka, Flink, processed-event
fan-out, historian, and operator observability endpoints.

## What It Measures

Each phase records simulator delivery, edge events, reconnects, historian
writes, aggregate consumer lag, Flink job state, API and AI health, Prometheus,
Kafka UI, Grafana, container CPU/memory, and the latency of the three operator
endpoints. Kafka UI and Grafana are observed as dependencies for operators;
they are not part of the industrial event-processing path.

The standard scenario contains warmup, sustained traffic, a burst, a source
reconnect, a Flink restart, recovery, and a drain period. The runner also
enables only the protocols declared by the scenario, so an idle connector is
not mistaken for a failed connector.

## Run It

Use an isolated Compose project when another Ravan stack is already running:

```powershell
$env:COMPOSE_PROJECT_NAME = "ravan-rehearsal"
Get-Content docker/rehearsal.env | ForEach-Object {
  if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
  }
}
py -3.13 -m services.cli.datastreamctl benchmark industrial-soak `
  --no-build --report-dir .datastream/industrial-soak --json
```

The default scenario runs for 900 seconds. Use `--smoke` only for a short
functional check; its compressed restart window is not sufficient evidence for
Flink recovery. The authoritative artifacts are `industrial-soak.json` and
`industrial-soak.md` in the selected report directory.

## Multi-Site Fan-In Soak

After the single-site connector soak, validate concurrent site traffic through
the shared Kafka/Flink/downstream path. This runner uses one independent host
generator per site and sends canonical-compatible events to
`industrial.normalized`; it does not replace the OPC UA/MQTT/Modbus connector
soak above.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/multi-site-live-soak.ps1 `
  -Seconds 900 -Sites 3 -RatePerSecond 100 -DeviceCount 50 `
  -KafkaBrokers localhost:29092 `
  -ComposeProject ravan-rehearsal `
  -ComposeEnvFile docker/rehearsal.env
```

The rehearsal broker derives its advertised external listener from
`KAFKA_HOST_PORT`; this is required when using `docker/rehearsal.env` rather
than the default Compose ports. The valid 2026-07-17 run acknowledged 269,994
events, persisted 269,994 industrial and 269,994 processed events across
three site IDs, reported zero DLQ rows, zero final fan-out lag, one running
Flink job, and no producer failures. Kafka UI and Grafana remained reachable;
the final single probes were 24.07 ms and 242.91 ms respectively. The AI
gateway was operational but degraded because the configured local model
returned HTTP 400, which is an optional-model integration result rather than a
stream-processing failure.

## Backup And Offline Checks

Run the isolated backup drill against the rehearsal project after the historian
migration has completed:

```powershell
$env:TIMESCALE_HOST = "localhost"
$env:TIMESCALE_PORT = "25433"
$env:TIMESCALE_USER = "stream"
$env:TIMESCALE_PASSWORD = "stream"
$env:TIMESCALE_DB = "stream_engine"
py -3.13 -m services.cli.datastreamctl backup-drill `
  --backup-dir .datastream/backup-validation `
  --restore-db stream_engine_restore_rehearsal `
  --report-dir .datastream/backup-validation --json
```

The local drill restored all four historian hypertables and matched the
before/after row counts (248,226 rows in the recorded run). It uses a Docker
`pg_dump`/`pg_restore` fallback when WAL-G is not installed. Continuous WAL
archiving, backup encryption, retention, and off-host restore remain operator
responsibilities.

For an air-gapped rehearsal, the Compose image manifest and image archive are
generated under `.datastream/offline-validation/`. The recorded bundle
contained all 16 referenced images, was 2.84 GiB, and had SHA-256
`BF6CFB3288570D89B25D2758A72750C6CA1CB4816E9018CAB2029407614B0716`.
Generated validation artifacts are intentionally not committed.

## Interpreting Results

`passed=true` means the configured end-of-campaign gates passed. It does not
claim a production throughput limit or real-device compatibility. A healthy
result should show a running Flink job, zero final aggregate lag, healthy
operator endpoints, and no acceptance failures. `null` connector counters
mean that the selected service profile did not expose that metric; they are
measurement gaps, not proof of zero errors. Confirm them with service logs or
add the connector metric before using the campaign for loss accounting.

The test should be repeated on representative target hardware before a plant
deployment. Physical PLC certification, firewall/TLS behavior, vendor gateway
behavior, retention sizing, and multi-node Kubernetes failure testing remain
deployment-owner acceptance work.

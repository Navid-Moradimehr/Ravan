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

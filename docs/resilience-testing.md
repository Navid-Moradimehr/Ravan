# Resilience Testing

The platform includes two complementary resilience test paths.

`datastreamctl benchmark resilience` is a deterministic, broker-free campaign
for local development and CI. It uses the canonical industrial event validator
and the same JSONL disk spool used by edge ingestion. It injects malformed
records, duplicate identities, out-of-order timestamps, and a simulated Kafka
outage. The report shows accepted and rejected records, queued and replayed
records, simulated historian writes, unaccounted records, pending spool data,
elapsed time, and peak memory.

Example:

```powershell
py -3.13 -m services.cli.datastreamctl benchmark resilience `
  --events 10000 `
  --outage-events 2000 `
  --report-dir .datastream/reports/resilience
```

The campaign is intentionally not presented as proof of Kafka or TimescaleDB
performance. It proves the local contracts and accounting behavior. Use the
Docker-backed `industrial-soak` command for live service throughput, broker
lag, container resource, restart, reconnect, and recovery measurements:

```powershell
py -3.13 -m services.cli.datastreamctl benchmark industrial-soak `
  --scenario config/benchmarks/industrial-soak.yaml `
  --smoke `
  --report-dir .datastream/reports/industrial-soak
```

For longer campaigns, omit `--smoke` or set `--duration`. Real site acceptance
still requires customer validation with their PLCs, network behavior, storage,
retention policy, and failure procedures.

## Interpreting Results

- `unaccounted_events=0` means every unique valid event was either written or
  replayed after the simulated outage.
- `pending_after_recovery=0` means the local spool drained completely.
- `rejected_events` is expected when malformed input injection is enabled.
- `duplicate_events` is an injected input condition; it must not increase the
  historian write count.
- `peak_memory_kb` is a local process measurement, not a production capacity
  guarantee.

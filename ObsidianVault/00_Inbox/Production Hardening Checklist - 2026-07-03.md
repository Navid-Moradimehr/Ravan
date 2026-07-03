# Production Hardening Checklist - 2026-07-03

## Focus

- multi-site rollout
- self-hosted security
- packaging later
- realistic simulator and benchmarks

## In Progress

- manifest/site identity validation gap
- execution checklist capture
- rollout acceptance report export
- multi-PLC simulator scenarios
- self-hosted secrets guidance

## Remaining

- signed release outputs
- target-hardware sizing validation
- restore/rollback drill measurement across at least two sites

## Notes

- Keep raw plant data local by default.
- Federation should only consume approved rollups or explicit bridge outputs.
- Packaging remains deferred until runtime and deployment shape are stable.
- The simulator now needs to be compared with repeated benchmark sessions, not one-off local runs.
- Operators should inject JWT, broker, historian, and model secrets from their own secret store.

## Measured Baseline

- `multi-plc-line`: 93,307.08 events/sec
- `burst-load`: 90,183.52 events/sec
- `dropout-reconnect`: 95,832.26 events/sec
- `industrial-benchmark`: 94,157.53 events/sec
- average: 93,370.10 events/sec

## Repeat Matrix

- `demo-site`: mean 86,376.50 events/sec, median 86,376.50, stdev 288.99, repeats 2
- `plant-a`: mean 94,552.48 events/sec, median 94,552.48, stdev 1,214.24, repeats 2

## Release Skeleton

- release-package command now emits `release-manifest.json` and `checksums.sha256`
- package output stays separate from future signed release artifacts

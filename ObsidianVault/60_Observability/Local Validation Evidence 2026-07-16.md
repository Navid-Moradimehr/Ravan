# Local Validation Evidence - 2026-07-16

## Passed without Docker

- Preflight contract validation.
- Local Kubernetes bundle rehearsal.
- Industrial soak dry-run.
- Three-site federation/outage simulation: 6,000 central events, zero
  duplicates, zero cross-site events, zero isolation errors, recovery complete.
- Fault campaign: 5,000 requested events, malformed/duplicate/out-of-order
  input, outage replay, zero unaccounted events, zero pending after recovery.
- Extended protocol, pipeline, model-data, lakehouse, governance, and Flink
  suites.

## Blocked by host environment

Docker Compose live state and the real 15-minute full-stack soak could not be
verified because Docker Desktop/WSL commands timed out. This is an environment
gate, not a passing or failing application result. Retry after Docker responds.

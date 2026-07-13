# Live Industrial Simulation: 2026-07-13

## Test Setup

Two 15-minute wall-clock live soaks were run on the same local machine against
the same Docker-backed downstream stack.

- Single-site run: one `services.ingestion.mock_generator` process at 100
  events/sec
- Multisite run: three `services.ingestion.mock_generator` processes at 100
  events/sec each

In both runs the baseline compose source simulators were stopped first so the
traffic was isolated to the live generator processes.

The Docker stack used the Flink runtime path. The current job overview showed
`iot-anomaly-processor` in `RUNNING` state with 2 running tasks.

## Final Results

Final historian-write counters captured after the runs:

| Run | industrial_events | processed_events | ai_enriched |
|---|---:|---:|---:|
| single-site | 2,226 | 2,210 | 1,754 |
| multisite | 3,049 | 3,036 | 2,171 |

Additional observations:

- fanout lag stayed at 0 for the final snapshots in both runs
- processed-fanout lag stayed at 0
- ai-fanout lag stayed at 0
- the multisite run did not fail the downstream pipeline, but it also did not
  scale linearly with the extra sites

## Interpretation

The local single-node setup is stable, but multisite load only produced about
37% more historian writes than the single-site run. That means the platform is
functional for multiple equal-rate sites, yet the node ceiling is visible.

This is useful for release planning:

- single-site deployments are the safest first target
- multisite deployments should be recommended only when the operator can add
  more capacity or accept lower per-site throughput
- additional nodes become a practical requirement before the platform reaches
  linear site growth

## Flink Note

The runtime is using Flink rather than the Python fallback. The JobManager REST
API reported:

- version: 1.20.0
- current job: `iot-anomaly-processor`
- tasks running: 2

There was an earlier transient failed job entry from a checkpoint directory
creation problem, but the active job remained healthy during the final soak.

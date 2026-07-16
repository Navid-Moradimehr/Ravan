# World Model Soak Campaign v3

## Status

Implemented on 2026-07-16. The local soak harness now produces a unique
campaign ID and directory, explicit episode boundary records, a manifest v3
bundle, and bounded downstream evidence.

## Evidence path

Telemetry is published to `industrial.normalized`; action, outcome, and
episode-boundary events are published to `industrial.operational`; artifact
references are published to `industrial.observation-artifacts`; artifacts are
uploaded to MinIO; Flink processes the normalized topic; fan-outs write the
historian and optional Iceberg tables; the compiler creates steps and
transitions for downstream model training.

## Acceptance checks

- Kafka producer acknowledgements have zero failures.
- V3 bundle counts include site-qualified channels, episodes, and transitions.
- Timescale checks exact campaign event IDs in `industrial_events` and
  `processed_events` without scanning the whole historian.
- Iceberg checks exact operational event and artifact IDs with predicate
  filters.
- MinIO downloads and hashes every campaign artifact.
- Flink REST reports at least one RUNNING job.

If a dependency is intentionally absent, `--skip-downstream-verify` can be
used for an isolated compiler test. That report must not be used as a
full-stack acceptance result.

## Run

```powershell
py -3.13 scripts/world-model-soak.py --seconds 900 --sites 3 --telemetry-rate 1
```

Reports are under
`.datastream/reports/world-model-soak/<campaign-id>/world-model-soak.json`,
with `latest.json` at the report root.

[[Model Dataset Manifest v3]]
[[Production Readiness Validation 2026-07-15]]

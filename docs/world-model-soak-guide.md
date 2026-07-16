# World-Model Evidence Soak

`scripts/world-model-soak.py` is a 15-minute local campaign designed to test
whether the platform records model-useful evidence, not merely whether it can
move scalar telemetry.

It publishes canonical telemetry for three sites and three channels per site,
publishes action/outcome and episode-boundary events, uploads small real
artifact objects to MinIO, publishes artifact references to Kafka, and compiles
the captured records into a manifest-v3 bundle.

## Run

```powershell
py -3.13 scripts/world-model-soak.py --seconds 900 --sites 3 --telemetry-rate 1
```

The runner starts the required Docker services with the `extended` and
`world-model` profiles. Reports are written to
`.datastream/reports/world-model-soak/<campaign-id>/`, with a stable
`latest.json` pointer at the report root.

## Evidence checked

- Kafka producer acknowledgements and failures
- Three-site identity preservation
- Telemetry, action, outcome, boundary, and artifact record counts
- Real MinIO object upload and SHA-256 reference
- Deterministic manifest-v3 compilation with site-qualified channels
- Explicit episode boundaries and whole-episode train/validation/test splits
- Transition rows linking current/next observations to action/outcome IDs
- Fixed-grid steps and missing-value masks
- Parquet bundle, lineage, semantic context, quality report, and `_SUCCESS`
- Exact downstream checks using bounded IDs for TimescaleDB, Iceberg, MinIO
  checksums, and Flink job state

This does not certify PLC drivers, real industrial networks, GPU training,
Kubernetes, or customer retention policies. The runner publishes directly to
the normalized Kafka boundary; protocol-specific connector certification
remains covered by the protocol edge-case matrix.

Use `--skip-downstream-verify` only for compiler-only or intentionally
isolated runs. It is not a passing full-stack result. Supply `--campaign-id`
for reproducibility; otherwise the runner generates one and uses it in event
metadata, episode IDs, artifact keys, the manifest, and report path.

## Current local evidence

The completed campaign before the schema-compatibility fix recorded 900
samples, 8,100 observations, 540 actions, 540 outcomes, and 90 artifact
references with 9,276/9,276 Kafka acknowledgements and a `RUNNING` Flink job.
Exact event-id checks found all 8,100 observations in both TimescaleDB tables,
and the compiled bundle passed its evidence gate.

That campaign also exposed that an old development
`industrial.operational_events` table had the telemetry schema, so operational
fields were not retained in that table. The sink now rejects this mismatch and
Compose defaults to `operational_events_v2`. After Docker Desktop 29.6.1 was
installed and restarted, the corrected 15-minute rerun completed with 900
samples, 8,100 observations, 540 actions, 540 outcomes, and 90 artifact
references; Kafka acknowledged 9,276/9,276 messages with zero failures. The
compiled bundle was valid with zero missing observation values.

## Post-restart lakehouse verification

After Docker Desktop was restarted, a live write-through probe published two
operational events and one artifact reference. The operational rows appeared
in `industrial.operational_events_v2` with intact `site_id`, `event_type`,
`entity_id`, and `payload_json`. The artifact row appeared in
`industrial.observation_artifacts` with its MinIO URI, byte size, and SHA-256.
Flink remained `RUNNING`, and the API health check reported Kafka and
historian healthy. The corrected campaign was also verified downstream using
exact IDs and a bounded campaign time window: TimescaleDB contained all 8,100
observations in both historian tables; `industrial.operational_events_v2`
contained 1,086 complete operational rows; `industrial.observation_artifacts`
contained all 90 artifact references; and all 90 MinIO objects matched their
recorded SHA-256 values. This is local evidence validation, not real PLC or
plant certification.

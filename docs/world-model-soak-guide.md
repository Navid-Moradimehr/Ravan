# World-Model Evidence Soak

`scripts/world-model-soak.py` is a 15-minute local campaign designed to test
whether the platform records model-useful evidence, not merely whether it can
move scalar telemetry.

It publishes canonical telemetry for three sites and three channels per site,
publishes action/outcome and episode-boundary events, uploads small real
artifact objects to MinIO, publishes artifact references to Kafka, and compiles
the captured records into a manifest-v2 bundle.

## Run

```powershell
py -3.13 scripts/world-model-soak.py --seconds 900 --sites 3 --telemetry-rate 1
```

The runner starts the required Docker services with the `extended` and
`world-model` profiles. Reports are written to
`.datastream/reports/world-model-soak/`.

## Evidence checked

- Kafka producer acknowledgements and failures
- Three-site identity preservation
- Telemetry, action, outcome, boundary, and artifact record counts
- Real MinIO object upload and SHA-256 reference
- Deterministic manifest-v2 compilation
- Fixed-grid steps and missing-value masks
- Parquet bundle, lineage, semantic context, quality report, and `_SUCCESS`

This does not certify PLC drivers, real industrial networks, GPU training,
Kubernetes, or customer retention policies. The runner publishes directly to
the normalized Kafka boundary; protocol-specific connector certification
remains covered by the protocol edge-case matrix.

## Current local evidence

The completed campaign before the schema-compatibility fix recorded 900
samples, 8,100 observations, 540 actions, 540 outcomes, and 90 artifact
references with 9,276/9,276 Kafka acknowledgements and a `RUNNING` Flink job.
Exact event-id checks found all 8,100 observations in both TimescaleDB tables,
and the compiled bundle passed its evidence gate.

That campaign also exposed that an old development
`industrial.operational_events` table had the telemetry schema, so operational
fields were not retained in that table. The sink now rejects this mismatch and
Compose defaults to `operational_events_v2`. A corrected 15-minute rerun must
be completed after Docker Desktop is healthy; the attempted rerun on
2026-07-16 was interrupted by Docker Desktop's Linux engine returning API 500
and Kafka `ApiVersionRequest` timeouts. It must not be counted as a platform
pass.

## Post-restart lakehouse verification

After Docker Desktop was restarted, a live write-through probe published two
operational events and one artifact reference. The operational rows appeared
in `industrial.operational_events_v2` with intact `site_id`, `event_type`,
`entity_id`, and `payload_json`. The artifact row appeared in
`industrial.observation_artifacts` with its MinIO URI, byte size, and SHA-256.
Flink remained `RUNNING`, and the API health check reported Kafka and
historian healthy. This is a current-path verification; the corrected full
15-minute campaign remains a separate acceptance run.

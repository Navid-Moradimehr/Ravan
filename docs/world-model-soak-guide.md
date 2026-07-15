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

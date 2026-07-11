# Training Dataset Guide

The platform does not train models. It creates reproducible, portable bundles
that users can train with PyTorch, JAX, Spark, Ray, Polars, or another local
stack.

## Manifest

Create a YAML manifest that identifies the site, time range, observation
topics/tables, alignment policy, provenance, and purpose. For JEPA, the
observation source is sufficient to start. For Dreamer and MuZero, the
manifest must also declare action sources, outcome sources, and episode
boundaries.

```yaml
dataset_id: packaging-line-dreamer-v1
site_id: plant-a
time_range: 2026-01-01/2026-04-01
purpose: dreamer
observation_sources:
  - industrial.normalized
action_sources:
  - industrial.operational
outcome_sources:
  - mes.outcomes
episode_definition:
  boundary: batch_id_or_changeover
alignment:
  sample_interval_ms: 1000
  max_lateness_ms: 2000
provenance:
  mapping_version: line-03-sources-v7
  topology_version: plant-a-topology-v4
splits:
  train: 2026-01-01/2026-03-01
  validation: 2026-03-01/2026-03-15
  test: 2026-03-15/2026-04-01
```

Validate it with:

```powershell
datastreamctl training-dataset validate config/training/packaging-line-dreamer.yaml
```

Compile exported JSONL, CSV, or Parquet-compatible records into a bundle:

```powershell
datastreamctl training-dataset compile `
  config/training/packaging-line-dreamer.yaml `
  data/training/packaging-line-dreamer-v1 `
  --observations exports/observations.jsonl `
  --operational-events exports/operational-events.jsonl `
  --outcomes exports/outcomes.jsonl
```

The output contains `observations.parquet`,
`operational_events.parquet`, `outcomes.parquet`, `manifest.yaml`,
`semantic_context.json`, `lineage.json`, and `quality-report.json`. Empty
tables are still emitted so downstream code has a predictable bundle shape.

The compiler does not silently interpolate, invent rewards, or merge sites.
Users must define their alignment and reward logic in the training code.

## Compile directly from Iceberg

Users with a MinIO or S3-backed Iceberg catalog can provide an explicit JSON
source configuration instead of exporting files first. Credentials remain in
the environment or catalog's secret configuration.

```json
{
  "catalog": {
    "name": "sql",
    "type": "sql",
    "uri": "${LAKEHOUSE_CATALOG_URI}",
    "warehouse": "${LAKEHOUSE_WAREHOUSE}"
  },
  "sources": {
    "observations": {"namespace": "industrial_plant-a", "table": "events"},
    "operational_events": {"namespace": "industrial_plant-a", "table": "operational_events"}
  }
}
```

Then run:

```powershell
datastreamctl training-dataset compile `
  config/training/plant-a-jepa.yaml `
  data/training/plant-a-jepa-v1 `
  --iceberg-sources config/training/iceberg-sources.json
```

This is an explicit batch read, not a background lakehouse service. Users
should bound the selected tables and time ranges, and should use the dataset
manifest for site, topology, provenance, and quality restrictions.

Every compiled bundle now includes non-blocking quality signals for duplicate
event IDs, missing source timestamps, and events arriving more than 60 seconds
after their source timestamp. These signals are evidence for dataset review;
they do not change the live ingestion acceptance policy.

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

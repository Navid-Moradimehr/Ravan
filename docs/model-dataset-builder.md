# Model Dataset Builder

The platform can prepare a deterministic, versioned evidence bundle for
downstream JEPA, Dreamer, MuZero, or conventional ML workflows. It does not
train a model, infer a reward, interpolate missing values, or execute control
actions.

## Manifest v2

```yaml
manifest_version: 2
dataset_id: plant-a-pump-v1
site_ids: [plant-a]
time_range:
  start: 2026-01-01T00:00:00Z
  end: 2026-01-01T01:00:00Z
purpose: dreamer
observation_sources: exports/observations.jsonl
action_sources: exports/actions.jsonl
outcome_sources: exports/outcomes.jsonl
episode_definition:
  boundary: industrial.boundary.v1
alignment:
  sample_interval_ms: 1000
  max_skew_ms: 250
provenance:
  source: historian-and-operational-events
semantic_context:
  topology_version: plant-a-v3
```

`observation_sources` may be a path, a list, or an inline list of records.
Each observation needs an asset/entity, channel/tag, numeric value, and a
parseable source timestamp. The compiler aligns each channel to a fixed grid
using nearest-neighbor matching within `max_skew_ms`. Missing values are
represented by masks; values are never silently forward-filled or
interpolated.

## CLI

```powershell
datastreamctl training-dataset validate config/datasets/pump-v2.yaml --json
datastreamctl training-dataset build config/datasets/pump-v2.yaml .datastream/datasets/pump-v1 --json
```

The output contains `steps.parquet`, `actions.parquet`, `outcomes.parquet`,
`artifacts.parquet`, `channels.json`, `semantic-context.json`,
`quality-report.json`, `lineage.json`, `manifest.yaml`, and `_SUCCESS`.

## Ownership boundary

The platform owns the contract, bounded alignment, masks, provenance files,
and deterministic local compiler. Users own source exports, episode truth,
reward/objective definitions, train/test policy, model code, GPU execution,
and any external lakehouse credentials. A v1 manifest remains supported by
the original training-dataset compiler.

## Optional durable worker

Register manifests and queue builds through the API only when Postgres is
available. The `world-model` Compose profile runs a worker using
`FOR UPDATE SKIP LOCKED`, so multiple workers can claim different jobs without
introducing duplicate builds:

```powershell
docker compose -f docker/docker-compose.yml --profile world-model up -d dataset-worker
```

The worker writes to a temporary/output directory selected by the operator and
marks a job successful only after the bundle contains `_SUCCESS`. Postgres
stores manifest versions, job state, heartbeats, errors, and output artifact
metadata. The worker is optional; direct CLI builds remain available for
offline or single-user deployments.

The web UI is available at `/datasets`. It validates a JSON representation of
the manifest and explains the platform/user ownership boundary. The CLI
remains the complete offline build interface; the UI intentionally does not
accept credentials or upload source data.

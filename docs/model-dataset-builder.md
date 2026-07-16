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

## Manifest v3: multi-site training evidence

Manifest v3 is the platform-owned contract for new multi-site model-data
bundles. It keeps v2 available for existing exports, but adds site-qualified
channel identity, explicit episode identity, deterministic whole-episode
splits, and a transition table.

```yaml
manifest_version: 3
dataset_id: company-pilot-v3
site_ids: [plant-a, plant-b, plant-c]
purpose: dreamer
observation_sources: exports/observations.jsonl
action_sources: exports/actions.jsonl
outcome_sources: exports/outcomes.jsonl
episode_definition:
  boundary: industrial.boundary.v1
alignment:
  sample_interval_ms: 1000
  max_skew_ms: 250
splits:
  strategy: episode_hash
  seed: 17
  ratios: {train: 0.7, validation: 0.15, test: 0.15}
provenance:
  source: historian-and-operational-events
semantic_context:
  topology_version: company-topology-v1
```

Every v3 observation must contain `site_id`, `asset_id` or `entity_id`, a
`tag` or `channel`, a numeric `value`, a parseable timestamp, and
`episode_id`, `context_id`, or `lineage_id`. A channel is represented as
`site_id::entity_id::tag`; two sites cannot accidentally share a feature
column. The compiler does not invent an episode, reward, interpolation, or
control action.

The v3 builder emits the existing files plus `transitions.parquet`. Each
transition contains current and next observations, the split, optional
action/outcome references, reward/terminal fields, and site/episode identity.
Splits are assigned to whole episodes, never individual rows. The default is
a deterministic SHA-256 episode hash with a recorded seed. Use
`splits.strategy: explicit` for supplied episode assignments, or
`splits.strategy: temporal` with `train_end` and `validation_end` boundaries
for chronological evaluation. Hash splits require at least three episodes;
smaller datasets must use explicit or temporal boundaries.

The v3 quality report includes episode and split counts, missing observation
masks, unlinked action/outcome counts, and the generated manifest hash. A
build fails on missing identity, duplicate observation event IDs, invalid
episode identity, or unit changes within one channel. This is a dataset
integrity gate, not a claim that the resulting data is suitable for a specific
model without user review.

## CLI

```powershell
datastreamctl training-dataset validate config/datasets/pump-v2.yaml --json
datastreamctl training-dataset build config/datasets/pump-v2.yaml .datastream/datasets/pump-v1 --json
```

The output contains `steps.parquet`, `actions.parquet`, `outcomes.parquet`,
`artifacts.parquet`, `channels.json`, `semantic-context.json`,
`quality-report.json`, `lineage.json`, `manifest.yaml`, and `_SUCCESS`.
Manifest v3 additionally emits `transitions.parquet` and site-qualified
channel metadata in `channels.json`.

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

The durable API surface includes `GET/POST /api/v1/datasets/manifests`,
`GET /api/v1/datasets/manifests/{dataset_id}/versions`,
`POST /api/v1/datasets/manifests/validate`, `GET/POST
/api/v1/datasets/builds`, `GET /api/v1/datasets/builds/{job_id}`, `POST
/api/v1/datasets/builds/{job_id}/cancel`, and `GET
/api/v1/datasets/builds/{job_id}/artifacts`.

The compiler benchmark is available as a Python library through
`services.benchmarks.model_dataset.run_benchmark`. It measures local manifest
read, bounded alignment, Parquet output, and quality artifact generation; it
does not represent Kafka, S3, GPU, or multi-node performance.

Current local reference: `1,000` records -> `1,000` aligned steps in `0.9512 s`
(`1,051.28 records/sec`) on the development machine. This is a compiler
reference only, not an end-to-end platform capacity claim.

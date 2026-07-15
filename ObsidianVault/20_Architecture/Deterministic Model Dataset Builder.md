# Deterministic Model Dataset Builder

## Boundary

The builder is an intelligence-plane preparation tool. It consumes platform
exports and produces a portable bundle for user-owned training code. It does
not become a model runtime and does not decide what a reward means.

## Contract

Manifest v2 identifies sites, time range, purpose, source records, alignment,
episode boundaries, provenance, and semantic context. Actions, outcomes, and
large artifacts remain separate from observations.

## Alignment

The compiler uses a fixed interval and explicit maximum timestamp skew. It
uses nearest records only within that bound and emits a boolean mask when no
valid observation exists. There is no silent interpolation, forward filling,
or cross-site merge.

## Outputs

`steps.parquet`, `actions.parquet`, `outcomes.parquet`, `artifacts.parquet`,
`channels.json`, `semantic-context.json`, `manifest.yaml`, `lineage.json`,
`quality-report.json`, and `_SUCCESS`.

## Future extension

The current compiler is local and deterministic. A durable Postgres-backed
build queue and optional worker are the next phase. External Iceberg/S3
scanning and multi-site federation must remain bounded and deployment-owned.

The optional `world-model` Compose profile now provides that queue worker.
Postgres claims jobs with `FOR UPDATE SKIP LOCKED`, and the worker records
success/failure plus emitted artifact files. The default deployment is
unchanged.

The `/datasets` web page provides a lightweight validation view. It is not a
training UI and does not upload data or handle secrets. CLI and worker paths
remain the authoritative build interfaces.

The API also supports manifest validation/version lookup and durable build
status, cancellation of queued jobs, and emitted artifact listing. These are
control-plane operations; they do not execute model training.

The local benchmark covers compiler work only. It must not be presented as a
substitute for site-level ingestion, Kafka, S3, GPU, or Kubernetes validation.

Reference result on 2026-07-16: 1,000 records compiled into 1,000 steps in
0.9512 seconds, or 1,051.28 records/sec. The full Python suite passed with
649 tests, the UI production build passed, and the Compose file rendered
successfully.

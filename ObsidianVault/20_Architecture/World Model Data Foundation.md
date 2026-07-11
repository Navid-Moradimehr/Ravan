# World Model Data Foundation

The platform is a data foundation, not a world-model training runtime. Core
capabilities are replayable telemetry, historian storage, optional Iceberg
over MinIO/S3, semantic context, operational-event transport, provenance, and
portable training bundles.

Users own plant-specific adapters, rewards, action semantics, episode
boundaries, safety constraints, retention, IAM, and model training. JEPA can
start from passive observations; Dreamer and MuZero require explicit actions,
outcomes, and episode context.
# Multi-Site World-Model Foundation Status

The platform supports a local-first data foundation. Each site can ingest,
process, store, replay, and operate independently. Cross-site world-model
collection is an optional extension and must not become a dependency of the
site-local historian path.

Current additive contracts:

- organization/project/site-qualified identity
- approved federation topic intent
- lakehouse layout intent
- clock and late-event quality policy

Schema-version-1 manifests remain valid. The default generated environment is
still `FEDERATION_ENABLED=false`, `LAKEHOUSE_LAYOUT=single-table`, and the
historian-only fan-out path.

Platform-owned: canonical event contracts, site identity fields, validation,
lineage, replay, historian integration, optional lakehouse adapters, and dataset
manifest contracts.

User-owned: plant topology, device credentials, network routes, broker
federation credentials, S3/MinIO credentials, retention, clock
synchronization, ontology content, GPU capacity, and model training.

Next implementation phases are optional Kafka federation, site-aware lakehouse
routing, raw archival, quality signals, and direct lakehouse dataset readers.

The dataset compiler now emits quality evidence for duplicate event IDs,
missing source timestamps, and late arrivals. This is intentionally a training
and curation gate, not a new live-ingestion rejection policy.

The live edge path now has a separate clock-quality policy. Raw payloads remain
replayable; `observe` and `warn` accept out-of-bound source timestamps with
telemetry, while `reject` routes the validated record to the DLQ before
normalized processing. Clock synchronization remains user-owned.

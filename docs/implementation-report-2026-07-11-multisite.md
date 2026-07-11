# Multi-Site Implementation Report: 2026-07-11

## Implemented

- Additive organization, project, site, and entity identity contracts.
- Manifest policies for approved federation topics, lakehouse layout, and
  timing quality.
- Optional Kafka MirrorMaker 2 Compose profile.
- Read-only `/api/v1/metadata/federation` contract endpoint.
- Optional site-aware Iceberg namespace/table routing.
- Optional raw Kafka-to-Iceberg archive profile.
- Explicit Iceberg-backed dataset compilation from MinIO/S3 catalogs.
- Dataset quality signals for duplicate IDs, missing source timestamps, and
  late events.
- Integrations-page entries explaining the new deployment-owned surfaces.
- Multi-site deployment and world-model user documentation mirrored in the
  Obsidian vault.

## Compatibility

The default single-site path is unchanged. Existing schema-version-1 manifests
load successfully. Federation, raw archival, and lakehouse routing are opt-in.
The historian-only fan-out remains the default when `SINKS` is not configured.

## Verification

- Python tests before this phase: `520 passed`, 4 pre-existing warnings.
- UI production build: passed, including TypeScript checking and all routes.
- Default Compose configuration: valid.
- Federation Compose profile: valid.
- Raw archive Compose profile: valid.
- Real-world simulator suite: average `80,908.50 events/sec`, p99 `0.0207 ms`.
- Site matrix: `demo-site` median `80,374.01 events/sec`; `plant-a` median
  `84,291.51 events/sec`; both passed the configured threshold.
- Multi-site outage simulation: 3 sites, 30,000 local events, 6,000 queued
  during outage, 30,000 centrally recovered, 0 duplicates.

## Not validated locally

No central Kafka cluster, WAN link, TLS/SASL setup, concurrent Iceberg writer,
or production S3 catalog was available. Therefore the MirrorMaker runtime,
cross-site catch-up, catalog commit contention, and real object-store failure
recovery still require deployment-side integration tests.

Real PLC/sensor certification also remains user-owned because the repository
only has protocol simulators and public/mock datasets.

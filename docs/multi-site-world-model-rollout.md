# Multi-Site World-Model Rollout

This guide explains how to use the platform when a company has several plants,
production lines, PLC networks, or independently operated sites.

## The simple path remains unchanged

For monitoring, alerts, replay, historian queries, and local dashboards, use
one site-local installation:

`devices -> connectors -> industrial.raw -> normalization -> industrial.normalized -> processing -> TimescaleDB`

No central broker, MinIO/S3 bucket, federation profile, or world-model dataset
configuration is required.

## Recommended multi-site path

Install one independent stack per plant. Each site owns its local broker,
historian, connector credentials, processing runtime, and operator dashboard.
Then replicate only approved normalized and operational topics to a central
Kafka cluster using the optional federation profile. A central controlled
consumer writes those events to an Iceberg catalog backed by MinIO or S3.

The central lakehouse is the source for company-wide training and analytics;
the site historian remains the low-latency operational source.

```text
Plant A devices -> Plant A stack -> local historian
                                  \-> approved Kafka federation --+
Plant B devices -> Plant B stack -> local historian              +-> central Kafka
Plant C devices -> Plant C stack -> local historian              +-> central Iceberg/S3
                                                                    \-> dataset bundles
```

## Alternative deployment approaches

### Independent sites with file export

Use when sites are air-gapped or have limited technical infrastructure. Each
site exports approved Parquet bundles or Kafka batches on a scheduled basis.
The company imports them into a central catalog. This is slower but easier to
audit and does not require a persistent WAN connection.

### Site-to-central Kafka federation

Use when near-real-time company visibility is required. MirrorMaker 2 or an
operator-managed Kafka replication system transfers approved topics. Sites
continue working during outages and catch up later.

### Central ingestion system

Use only when the plant network and operational policy permit a central system
to reach all PLCs and sensors. This reduces local installations but creates a
larger network and failure boundary. The platform supports the event model, but
users must provide routing, segmentation, certificates, and connector
placement.

## Platform-owned versus user-owned

Platform-owned:

- protocol connector interfaces and canonical event contracts
- site and source identity fields
- Kafka topic contracts and replay boundaries
- deterministic processing and historian fan-out
- optional Kafka federation profile
- optional raw archive profile
- Iceberg sink and site-aware routing
- dataset manifests, lineage, and quality reports

User-owned:

- PLC/sensor network access and credentials
- site topology, asset aliases, and ontology content
- central Kafka provisioning and security
- MinIO/S3, catalog, IAM, retention, compaction, and backups
- WAN routing and outage policy
- GPU/model capacity and training code
- action, reward, episode, and control semantics for Dreamer or MuZero

## World-model preparation

For JEPA-style representation learning, collect synchronized observations,
source and ingest timestamps, topology snapshots, units, calibration, operating
modes, maintenance context, and document references.

For Dreamer or MuZero, add operational events describing actions and outcomes,
episode boundaries, rewards, safety constraints, and operator approvals. The
platform can store and package these contracts; it cannot infer their meaning
from telemetry alone.

Compile only approved tables and sites with:

```powershell
datastreamctl training-dataset compile `
  config/training/company-model.yaml `
  data/training/company-model-v1 `
  --iceberg-sources config/training/iceberg-sources.json
```

Review `quality-report.json` and `lineage.json` before training. Do not treat a
successful compile as proof that the data is physically or causally sufficient
for a world model.

For a central writer, run `python -m services.federation.kafka_lakehouse_bridge`
in the central environment with `CENTRAL_KAFKA_BROKERS`,
`FEDERATION_INPUT_TOPIC`, and the lakehouse variables configured. The bridge
rejects topics that are not in `FEDERATION_ALLOWED_TOPICS` when policy
enforcement is enabled.

Inspect `/api/v1/observability/federation` for the latest adapter status. A
missing status file is reported as `unknown`; it is not treated as healthy.

## Failure behavior

- Site-local ingestion does not depend on the central broker.
- A federation outage increases central lag but does not stop local historian writes.
- A lakehouse failure is recoverable from Kafka retention and replay.
- Identity or topology conflicts are reported during manifest validation.
- Data-quality warnings appear in dataset reports without rejecting ordinary
  live ingestion by default.

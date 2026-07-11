# Lakehouse And External S3 Guide

The historian remains the default operational store. The optional lakehouse
path archives normalized industrial events in Apache Iceberg tables backed by
S3-compatible object storage. MinIO is the local reference deployment; AWS S3,
an S3-compatible appliance, or a company-managed object store can be used by
changing deployment configuration.

## Local Compose path

Start the extended profile and enable the lakehouse sink:

```powershell
$env:FANOUT_SINKS = "historian,lakehouse"
docker compose -f docker/docker-compose.yml --profile extended up -d
```

The profile starts MinIO, creates the `lakehouse` bucket, uses the existing
Timescale/Postgres service as the PyIceberg SQL catalog, and writes table data
to MinIO. The SQL catalog dependency is included in the platform image. The
platform does not require a cloud account for this path.

The SQL catalog stores Iceberg table metadata; MinIO stores Parquet data and
Iceberg metadata files. They are different responsibilities and both must be
backed up.

## External S3 path

Keep the historian enabled and replace the object-storage settings with values
owned by the deployment:

```dotenv
FANOUT_SINKS=historian,lakehouse
LAKEHOUSE_CATALOG=sql
LAKEHOUSE_CATALOG_URI=postgresql+psycopg2://user:password@catalog-db:5432/iceberg_catalog
LAKEHOUSE_NAMESPACE=industrial
LAKEHOUSE_TABLE=events
LAKEHOUSE_WAREHOUSE=s3://company-industrial-lakehouse/
LAKEHOUSE_S3_ENDPOINT=https://s3.amazonaws.com
LAKEHOUSE_S3_REGION=eu-west-1
LAKEHOUSE_S3_ACCESS_KEY=<deployment-managed-reference>
LAKEHOUSE_S3_SECRET_KEY=<deployment-managed-secret>
```

For AWS S3, an empty endpoint can be used when the deployment provides AWS
credential resolution through its runtime environment. For S3-compatible
systems, set the vendor endpoint and required addressing or TLS settings in
the deployment environment. Never commit credentials to the repository.

The SQL catalog is the reference default. A company may instead use an
external Iceberg REST catalog by setting `LAKEHOUSE_CATALOG=rest`, supplying a
catalog URI supported by PyIceberg, and configuring its authentication outside
the application. The REST service owns catalog authentication and table
coordination; the platform only uses the configured catalog client.

## What the platform writes

The lakehouse sink receives normalized events from `industrial.normalized`.
New tables preserve event ID, source and ingest times, site, line, source
identity, asset, tag, value, quality, unit, schema version, event stage, and
available mapping/configuration provenance. Existing older tables remain
append-compatible; a migration or a new table is required before expecting
new columns in an already-created table.

The normalized lakehouse consumer archives normalized events and their
available payload metadata. The raw Kafka topic remains the authoritative
replay boundary for ordinary installations. A company that does not use the
optional archive can export `industrial.raw` with a user-managed
Kafka/Iceberg connector after reviewing retention, privacy, and industrial
network data policies.

An optional `raw-archive` Compose profile is now available for deployments
that explicitly approve raw archival. It writes raw envelopes to a separate
`raw_events` table and never changes the normalized historian path. It remains
disabled by default; users must still define retention, redaction, access
control, and bucket lifecycle policies.

## Operational ownership

The platform owns the sink contract, table-writing code, and health failures.
The deployment owns the S3 bucket, catalog database or REST catalog, IAM,
retention, lifecycle policies, encryption, backup, network routing, and
credential rotation. A lakehouse sink failure must not replace the historian
as the live operational dependency; configure alerting and a durable Kafka
retention policy for recovery.

## Training-data limitation

This sink archives observations. A JEPA dataset can begin from these records,
but Dreamer/MuZero datasets also need user-supplied actions, outcomes, episode
boundaries, and reward semantics. Those are covered by the operational-event
and training-dataset contracts, not inferred from sensor values.

## Site-aware routing

The default remains `LAKEHOUSE_LAYOUT=single-table`, preserving the existing
deployment. A central multi-site deployment may opt into
`LAKEHOUSE_LAYOUT=per-site`; events are then routed to a namespace per site,
such as `industrial_plant-a.events`. Set
`LAKEHOUSE_NAMESPACE_TEMPLATE` and `LAKEHOUSE_TABLE_TEMPLATE` when a different
naming convention is required. Site routing is based on the event's `site`
field and does not merge local asset identities.

The platform does not enable concurrent direct writes from every plant by
itself. Operators should prefer a central controlled writer or a catalog with
documented multi-writer commit guarantees. Partitioning, compaction, catalog
availability, and S3 lifecycle policy remain deployment responsibilities.

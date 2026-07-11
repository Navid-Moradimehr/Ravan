# Lakehouse Routing

The historian remains the operational hot store. Iceberg backed by MinIO or
S3 is optional analytical and training storage.

Default behavior is unchanged: `single-table` routing and historian-only fanout
for ordinary installations. The optional `per-site` layout routes normalized
events to separate site namespaces while preserving the event's site and
source identity. The optional `shared-partitioned` layout keeps a single
Iceberg table but partitions it by `site` for controlled multi-site central
writes. This is the recommended starting point for central company collection
when one writer owns the lakehouse because it limits accidental cross-site
mixing without multiplying table names.

Platform-owned: sink interface, schema projection, site-aware routing, and
append failure behavior.

User-owned: catalog, bucket, credentials, TLS/IAM, retention, compaction,
partition strategy, central writer topology, and migration/backfill approval.

Raw archival is a separate opt-in consumer for `industrial.raw`. It writes a
raw envelope table and is disabled by default. The raw topic remains the
replay boundary for ordinary installations.

The archive can enforce a maximum payload size, redact configured top-level
fields, and publish rejected records to a user-selected DLQ topic.

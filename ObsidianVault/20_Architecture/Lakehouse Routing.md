# Lakehouse Routing

The historian remains the operational hot store. Iceberg backed by MinIO or
S3 is optional analytical and training storage.

Default behavior is unchanged: `single-table` routing and historian-only fanout
for ordinary installations. The optional `per-site` layout routes normalized
events to separate site namespaces while preserving the event's site and
source identity. This is the recommended starting point for central company
collection because it limits accidental cross-site mixing.

Platform-owned: sink interface, schema projection, site-aware routing, and
append failure behavior.

User-owned: catalog, bucket, credentials, TLS/IAM, retention, compaction,
partition strategy, central writer topology, and migration/backfill approval.

Raw archival is a separate opt-in consumer for `industrial.raw`. It writes a
raw envelope table and is disabled by default. The raw topic remains the
replay boundary for ordinary installations.

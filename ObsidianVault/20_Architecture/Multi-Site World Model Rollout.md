# Multi-Site World Model Rollout

Recommended topology: independent site-local stacks, optional approved-topic
Kafka federation, central Iceberg/MinIO or S3 storage, and explicit dataset
compilation. The lakehouse may use `single-table`, `per-site`, or
`shared-partitioned` layouts depending on whether the company wants one table,
one namespace per site, or one centrally managed table with site partitions.

The simple ingestion path remains the default and is not changed by enabling
the new contracts. Sites continue to operate during central outages.

Decision options:

- local-only for monitoring and historian use cases
- scheduled export/import for air-gapped sites
- MirrorMaker/Kafka federation for near-real-time central visibility
- central ingestion only when plant networking permits it

The platform provides contracts and adapters. Operators provide topology,
credentials, broker/catalog infrastructure, retention, security, and training
semantics.

Manifest lint also checks identity ownership. Two physical sources may observe
the same logical `site/asset/tag`, but the manifest must declare that intent in
a `site_asset_tag` correlation group. This prevents downstream consumers from
silently treating duplicate PLC/sensor observations as one authoritative value.

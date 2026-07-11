# Multi-Site World Model Rollout

Recommended topology: independent site-local stacks, optional approved-topic
Kafka federation, central Iceberg/MinIO or S3 storage, and explicit dataset
compilation.

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

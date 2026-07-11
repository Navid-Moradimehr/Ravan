# Multi-Site Federation

The default installation is site-local. A plant continues to ingest, process,
write to TimescaleDB, and operate its dashboard without a central network.

For company-wide datasets, enable the optional Kafka federation profile only
after the central Kafka cluster and its security configuration are supplied by
the operator. The reference profile mirrors normalized and operational topics;
raw events remain excluded unless the company explicitly approves them.

Platform handles:

- topic and event contracts
- site identity fields
- federation topic declarations
- validation and read-only federation metadata
- downstream sink and dataset interfaces

Users handle:

- central broker provisioning
- TLS/SASL credentials and network routes
- MirrorMaker capacity and retention
- cross-site data approval
- central Iceberg catalog and S3/MinIO credentials

Check the contract with:

```powershell
datastreamctl project-manifest validate config/project-manifest.yaml
```

Inspect the non-secret API view at `/api/v1/metadata/federation`. Use the
federation Compose profile only for a deliberate central transport deployment.

# Lakehouse And External S3

The optional lakehouse path uses Apache Iceberg tables over MinIO or another
S3-compatible object store. The local Compose reference uses a Postgres-backed
SQL catalog and MinIO for data files. External deployments may use AWS S3,
company S3 appliances, or an Iceberg REST catalog.

The platform does not treat an S3 bucket as a catalog. The catalog stores table
metadata and coordinates commits; the bucket stores Parquet and Iceberg files.
Both require backup and deployment-owned access controls.

Reference configuration:

```text
FANOUT_SINKS=historian,lakehouse
LAKEHOUSE_CATALOG=sql
LAKEHOUSE_CATALOG_URI=postgresql+psycopg2://.../iceberg_catalog
LAKEHOUSE_WAREHOUSE=s3://company-industrial-lakehouse/
LAKEHOUSE_S3_ENDPOINT=https://s3.amazonaws.com
LAKEHOUSE_S3_REGION=eu-west-1
```

The historian remains the operational default. The lakehouse is an optional
analytical/training archive and is not required for live monitoring.

User-owned responsibilities include bucket/catalog creation, IAM, TLS,
retention, encryption, backups, credential injection, and external S3 network
access. Raw payload archival is opt-in.

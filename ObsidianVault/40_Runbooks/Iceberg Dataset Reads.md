# Iceberg Dataset Reads

The platform's default write path is local historian plus Kafka. Dataset
compilation can optionally read selected Iceberg tables from MinIO or S3.

The user supplies a JSON catalog/table selection and keeps credentials outside
the repository. The compiler produces the same portable Parquet bundle,
manifest, lineage, and quality report as file-backed compilation.

This is a deliberate batch operation. It does not turn the dashboard into a
lakehouse query engine and it does not automatically scan every table.

Use an explicit Iceberg `row_filter` for bounded scans. Dataset manifests can
also define quality gates; failed gates produce evidence but return
`valid: false` to release automation.

Gates are opt-in. Without configured thresholds, quality signals remain
informational and do not invalidate the bundle.

# Optional MLflow Adapter

The platform includes an optional REST adapter for MLflow tracking and model
registry operations. It is not required by Kafka, the historian, dashboards, or
AI reporting, and it does not import the `mlflow` Python package.

## What it does

The adapter can:

- find or create an experiment;
- create a training run;
- log dataset, site, asset, and training parameters;
- log evaluation metrics;
- log model and lineage tags;
- register a model version from a user-owned model URI.

The adapter does not upload artifacts, train models, schedule GPUs, or serve
predictions. Artifacts remain in the user's configured local filesystem, MinIO,
or S3-compatible store. The returned MLflow run/model identifiers should be
stored with the platform dataset and model metadata.

## Configuration

```powershell
$env:MLFLOW_TRACKING_URI = "http://localhost:5000"
$env:MLFLOW_TRACKING_TOKEN = "user-owned-token-if-required"
$env:MLFLOW_TIMEOUT_SECONDS = "15"
```

Use `MLflowAdapterConfig.from_env()` and call `log_training_run()` from the
user's training code. A training run should include at least `dataset_id`,
`dataset_version`, `site_id`, `time_range`, and the feature-contract version.

## Recommended flow

```text
platform historian/lakehouse
        -> dataset builder
        -> user XGBoost/PyTorch/JEPA training code
        -> MLflow adapter
        -> MLflow run and model registry
        -> user inference service
        -> versioned Kafka prediction event
```

The adapter is intentionally a control-plane integration. It should not be
placed in the hot sensor-to-Kafka path.

# MLflow Adapter Guide

The MLflow integration is an optional REST adapter, not a required platform
service. It logs industrial dataset and lineage metadata, parameters, metrics,
and model registrations to a user-owned MLflow server. It does not train,
serve, or upload model artifacts.

Artifacts belong in the user's local filesystem, MinIO, or S3-compatible store.
Use the platform dataset ID/version and site/asset scope as MLflow tags. Return
MLflow `run_id` and model version to the platform metadata layer or prediction
event.

Keep the adapter outside the hot Kafka ingestion path. It is compatible with
XGBoost, LightGBM, CatBoost, scikit-learn, PyTorch, and user-owned transfer
learning code because it records lifecycle metadata rather than imposing a
training framework.

# Model Lifecycle Ledger

## Status

Implemented on 2026-07-16. This is a lightweight platform-core ledger, not a
replacement for MLflow.

## Platform responsibility

The ledger records model versions, dataset/manifest lineage, evaluation
results, explicit promotion states, rollback history, and the active model
boundary. It requires a passing evaluation before approval and never performs
automatic model activation or PLC actions.

## User responsibility

Users provide model artifacts, training code, metrics, evaluation policy,
GPU/runtime infrastructure, approval decisions, and optional MLflow. MLflow
sync is an adapter and does not become a runtime dependency.

## APIs

- `GET/POST /api/v1/modeling/model-versions`
- `GET /api/v1/modeling/model-versions/{model_id}`
- `POST .../{model_id}/evaluations`
- `POST .../{model_id}/transitions`
- `POST .../{model_id}/rollback`
- `GET .../{model_id}/history`
- `POST .../{model_id}/sync-mlflow`

Compose persists the ledger on the existing `api-data` volume at
`/data/model-lifecycle.json`. Multi-replica deployments must provide a shared
operator-managed metadata store before using concurrent lifecycle writes.

[[Model Dataset Manifest v3]]
[[Production Readiness Action Plan]]

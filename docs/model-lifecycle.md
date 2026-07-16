# Model Lifecycle Ledger

The platform provides a small provider-neutral lifecycle ledger for model
versions. It records model identity, provider, artifact URI, dataset and
manifest lineage, evaluations, explicit state transitions, and rollback
history. It does not train models, copy model artifacts, size GPUs, or
replace an active model automatically.

## States and required flow

`candidate -> evaluated -> approved -> active -> retired`

Rejected versions can return to `candidate` for another evaluation. Approval
requires at least one passing evaluation. Activating a version retires the
currently active version for the same model name and site. Rollback is an
explicit operator request and selects the most recently updated approved or
retired sibling version. Every registration, evaluation, transition, and
rollback is recorded in history.

## API

```powershell
$base = "http://localhost:8020"
$body = @{ model_name = "pump-world-model"; version = "2026.07.16.1"; provider = "local"; model_type = "dreamer"; artifact_uri = "s3://lakehouse/models/pump/1"; dataset_id = "company-pilot-v3"; manifest_hash = "..."; site_id = "plant-a" } | ConvertTo-Json
$model = Invoke-RestMethod "$base/api/v1/modeling/model-versions" -Method Post -Body $body -ContentType "application/json"

Invoke-RestMethod "$base/api/v1/modeling/model-versions/$($model.model_id)/evaluations" -Method Post -Body (@{ dataset_id = "company-pilot-v3"; metrics = @{ validation_loss = 0.12 }; passed = $true; evaluator = "offline-gate" } | ConvertTo-Json) -ContentType "application/json"
Invoke-RestMethod "$base/api/v1/modeling/model-versions/$($model.model_id)/transitions" -Method Post -Body (@{ target_state = "approved"; reason = "offline gate passed" } | ConvertTo-Json) -ContentType "application/json"
Invoke-RestMethod "$base/api/v1/modeling/model-versions/$($model.model_id)/transitions" -Method Post -Body (@{ target_state = "active"; reason = "operator activation" } | ConvertTo-Json) -ContentType "application/json"
Invoke-RestMethod "$base/api/v1/modeling/model-versions/$($model.model_id)/history"
```

The existing `GET /api/v1/modeling/models` response now includes role
bindings and ledger versions. The lifecycle endpoints remain usable without
platform authentication in the development configuration, while an operator
can put them behind the deployment's own API gateway and identity policy.

## MLflow integration

`POST /api/v1/modeling/model-versions/{model_id}/sync-mlflow` uses the existing
HTTP adapter and `MLFLOW_TRACKING_URI` configuration. It registers the model
artifact and tags it with the platform model ID, dataset ID, and manifest
hash. No `mlflow` Python package is imported by the platform. If MLflow is not
deployed or the request fails, the internal ledger remains authoritative and
the API returns an explicit integration error.

## Storage and ownership

Compose stores the ledger at `/data/model-lifecycle.json` on the existing
`api-data` volume. A deployment that runs multiple API replicas should replace
the file-backed path with a shared, operator-managed metadata database before
claiming concurrent multi-node lifecycle operation. Users own model code,
training runs, approval personnel, artifact storage credentials, and the
meaning of evaluation metrics.

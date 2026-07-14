import httpx

from services.integrations.mlflow_adapter import MLflowAdapter, MLflowAdapterConfig


def test_mlflow_adapter_tracks_industrial_run_without_mlflow_package():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        if request.url.path.endswith("get-by-name"):
            return httpx.Response(404, json={"error_code": "RESOURCE_DOES_NOT_EXIST"})
        if request.url.path.endswith("experiments/create"):
            return httpx.Response(200, json={"experiment_id": "7"})
        if request.url.path.endswith("runs/create"):
            return httpx.Response(200, json={"run": {"info": {"run_id": "run-1"}}})
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = MLflowAdapter(MLflowAdapterConfig("http://mlflow.local"), client=client)
    run = adapter.log_training_run(
        experiment_name="plant-a-maintenance",
        parameters={"dataset_id": "plant-a-v1", "trees": 100},
        metrics={"f1": 0.91},
        tags={"site_id": "plant-a", "model_family": "xgboost"},
    )
    assert run.run_id == "run-1"
    assert any(path.endswith("runs/log-parameter") for _, path, _ in calls)
    assert any(path.endswith("runs/log-metric") for _, path, _ in calls)
    assert any(path.endswith("runs/set-tag") for _, path, _ in calls) is False
    adapter.close()


def test_mlflow_adapter_registers_model_and_version_tags():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("model-versions/create"):
            return httpx.Response(200, json={"model_version": {"version": "3"}})
        return httpx.Response(200, json={})

    adapter = MLflowAdapter(MLflowAdapterConfig("http://mlflow.local"), client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = adapter.register_model("pump-failure", "runs:/run-1/model", run_id="run-1", tags={"dataset_id": "plant-a-v1"})
    assert result["model_version"]["version"] == "3"

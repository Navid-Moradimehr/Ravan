"""Optional MLflow tracking and model-registry adapter.

This module intentionally uses MLflow's HTTP API instead of importing the
``mlflow`` package. The platform therefore remains usable without MLflow, and
air-gapped deployments can point the adapter at a local MLflow server.
Artifacts are not copied by this adapter; callers provide an artifact/model
URI backed by their configured local filesystem, MinIO, or S3-compatible store.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

import httpx


class MLflowAdapterError(RuntimeError):
    """Raised when the optional MLflow control-plane API rejects a request."""


@dataclass(frozen=True)
class MLflowAdapterConfig:
    tracking_uri: str
    token: str | None = None
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "MLflowAdapterConfig":
        return cls(
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
            token=os.getenv("MLFLOW_TRACKING_TOKEN") or None,
            timeout_seconds=float(os.getenv("MLFLOW_TIMEOUT_SECONDS", "15")),
        )


@dataclass(frozen=True)
class MLflowRunReference:
    experiment_id: str
    run_id: str
    experiment_name: str


class MLflowAdapter:
    """Small, synchronous bridge for dataset/training metadata.

    The adapter does not consume Kafka, query the historian, upload artifacts,
    or deploy models. Those responsibilities stay with the caller and the
    platform's existing dataset contracts.
    """

    def __init__(self, config: MLflowAdapterConfig, client: httpx.Client | None = None):
        self.config = config
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {config.token}"} if config.token else {}
        self.client = client or httpx.Client(timeout=config.timeout_seconds, headers=headers)
        self.base_url = config.tracking_uri.rstrip("/")

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "MLflowAdapter":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise MLflowAdapterError(f"MLflow request failed: {exc}") from exc
        if not response.is_success:
            detail = response.text[:500]
            raise MLflowAdapterError(f"MLflow returned HTTP {response.status_code}: {detail}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise MLflowAdapterError("MLflow returned a non-JSON response") from exc
        if not isinstance(payload, dict):
            raise MLflowAdapterError("MLflow returned an unexpected response shape")
        return payload

    def get_or_create_experiment(self, name: str, *, artifact_location: str | None = None) -> str:
        """Return an experiment ID without creating duplicates."""
        path = f"/api/2.0/mlflow/experiments/get-by-name?experiment_name={quote(name, safe='')}"
        try:
            payload = self._request("GET", path)
            return str(payload["experiment"]["experiment_id"])
        except MLflowAdapterError as exc:
            if "HTTP 404" not in str(exc):
                raise
        body: dict[str, Any] = {"name": name}
        if artifact_location:
            body["artifact_location"] = artifact_location
        payload = self._request("POST", "/api/2.0/mlflow/experiments/create", json=body)
        return str(payload["experiment_id"])

    def create_run(self, experiment_id: str, *, tags: Mapping[str, str] | None = None) -> MLflowRunReference:
        payload = self._request(
            "POST",
            "/api/2.0/mlflow/runs/create",
            json={
                "experiment_id": experiment_id,
                "start_time": int(time.time() * 1000),
                "tags": _entries(tags),
            },
        )
        info = payload.get("run", {}).get("info", {})
        run_id = str(info.get("run_id", ""))
        if not run_id:
            raise MLflowAdapterError("MLflow did not return a run_id")
        return MLflowRunReference(experiment_id=experiment_id, run_id=run_id, experiment_name="")

    def log_parameters(self, run_id: str, parameters: Mapping[str, Any]) -> None:
        for key, value in parameters.items():
            self._request("POST", "/api/2.0/mlflow/runs/log-parameter", json={"run_id": run_id, "key": str(key), "value": str(value)})

    def log_metrics(self, run_id: str, metrics: Mapping[str, float], *, step: int = 0) -> None:
        timestamp = int(time.time() * 1000)
        for key, value in metrics.items():
            self._request(
                "POST",
                "/api/2.0/mlflow/runs/log-metric",
                json={"run_id": run_id, "key": str(key), "value": float(value), "timestamp": timestamp, "step": step},
            )

    def set_tags(self, run_id: str, tags: Mapping[str, str]) -> None:
        for key, value in tags.items():
            self._request("POST", "/api/2.0/mlflow/runs/set-tag", json={"run_id": run_id, "key": str(key), "value": str(value)})

    def register_model(self, name: str, source: str, *, run_id: str | None = None, tags: Mapping[str, str] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name, "source": source}
        if run_id:
            body["run_id"] = run_id
        result = self._request("POST", "/api/2.0/mlflow/model-versions/create", json=body)
        if tags and result.get("model_version", {}).get("version"):
            version = result["model_version"]["version"]
            for key, value in tags.items():
                self._request("POST", "/api/2.0/mlflow/model-versions/set-tag", json={"name": name, "version": str(version), "key": str(key), "value": str(value)})
        return result

    def log_training_run(
        self,
        *,
        experiment_name: str,
        parameters: Mapping[str, Any] | None = None,
        metrics: Mapping[str, float] | None = None,
        tags: Mapping[str, str] | None = None,
        artifact_location: str | None = None,
    ) -> MLflowRunReference:
        """Create a run and log platform dataset/lineage metadata."""
        experiment_id = self.get_or_create_experiment(experiment_name, artifact_location=artifact_location)
        created = self.create_run(experiment_id, tags=tags)
        run = MLflowRunReference(experiment_id=created.experiment_id, run_id=created.run_id, experiment_name=experiment_name)
        if parameters:
            self.log_parameters(run.run_id, parameters)
        if metrics:
            self.log_metrics(run.run_id, metrics)
        return run


def _entries(values: Mapping[str, Any] | None) -> list[dict[str, str]]:
    return [{"key": str(key), "value": str(value)} for key, value in (values or {}).items()]

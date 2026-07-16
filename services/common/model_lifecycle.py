"""Provider-neutral model evaluation and promotion ledger.

The ledger is intentionally smaller than MLflow. It records the platform
contract that must remain true regardless of the training tool: a model
version, its dataset lineage, evaluations, explicit state transitions, and
rollback history. MLflow can be synchronized through the optional adapter;
the platform does not import or require the MLflow package.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODEL_STATES = {"candidate", "evaluated", "approved", "active", "rejected", "retired"}
ALLOWED_TRANSITIONS = {
    "candidate": {"evaluated", "rejected"},
    "evaluated": {"candidate", "approved", "rejected"},
    "approved": {"active", "rejected"},
    "active": {"retired"},
    "rejected": {"candidate"},
    "retired": {"candidate"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelLifecycleError(ValueError):
    """Raised when a model lifecycle request violates the ledger contract."""


class ModelLifecycleLedger:
    """Small durable JSON ledger suitable for Compose and air-gapped sites."""

    def __init__(self, state_path: str | os.PathLike[str] | None = None):
        self._state_path = Path(state_path) if state_path else None
        self._models: dict[str, dict[str, Any]] = {}
        self._history: list[dict[str, Any]] = []
        self._load()

    @classmethod
    def from_env(cls) -> "ModelLifecycleLedger":
        return cls(os.getenv("MODEL_LIFECYCLE_PATH"))

    def register(
        self,
        *,
        model_name: str,
        version: str,
        provider: str,
        model_type: str = "unknown",
        artifact_uri: str = "",
        dataset_id: str = "",
        manifest_hash: str = "",
        site_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model_name = model_name.strip()
        version = version.strip()
        if not model_name or not version or not provider.strip():
            raise ModelLifecycleError("model_name, version, and provider are required")
        model_id = f"{model_name}:{version}"
        existing = self._models.get(model_id)
        if existing:
            if existing["state"] not in {"candidate", "rejected", "retired"}:
                raise ModelLifecycleError(f"model version already exists in state {existing['state']}: {model_id}")
            return dict(existing)
        record = {
            "model_id": model_id,
            "model_name": model_name,
            "version": version,
            "provider": provider,
            "model_type": model_type,
            "artifact_uri": artifact_uri,
            "dataset_id": dataset_id,
            "manifest_hash": manifest_hash,
            "site_id": site_id,
            "state": "candidate",
            "metadata": metadata or {},
            "evaluations": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        self._models[model_id] = record
        self._record_history(model_id, "registered", "candidate", "", "system")
        self._persist()
        return dict(record)

    def evaluate(
        self,
        model_id: str,
        *,
        dataset_id: str,
        metrics: dict[str, float],
        passed: bool,
        evaluator: str = "unknown",
        notes: str = "",
    ) -> dict[str, Any]:
        record = self._require(model_id)
        if record["state"] not in {"candidate", "evaluated"}:
            raise ModelLifecycleError(f"model must be candidate or evaluated before evaluation: {model_id}")
        evaluation = {
            "evaluation_id": str(uuid.uuid4()),
            "dataset_id": dataset_id,
            "metrics": {str(key): float(value) for key, value in metrics.items()},
            "passed": bool(passed),
            "evaluator": evaluator,
            "notes": notes,
            "created_at": _now(),
        }
        record["evaluations"].append(evaluation)
        record["state"] = "evaluated"
        record["updated_at"] = _now()
        self._record_history(model_id, "evaluated", record["state"], evaluation["evaluation_id"], evaluator)
        self._persist()
        return dict(record)

    def transition(self, model_id: str, target_state: str, *, reason: str, actor: str = "operator") -> dict[str, Any]:
        if target_state not in MODEL_STATES:
            raise ModelLifecycleError(f"unsupported model state: {target_state}")
        record = self._require(model_id)
        current_state = str(record["state"])
        if target_state == "approved" and not any(item.get("passed") for item in record["evaluations"]):
            raise ModelLifecycleError("model requires a passing evaluation before approval")
        if target_state not in ALLOWED_TRANSITIONS.get(current_state, set()):
            raise ModelLifecycleError(f"invalid model transition: {current_state} -> {target_state}")
        if target_state == "active":
            for other in self._models.values():
                if other["model_name"] == record["model_name"] and other.get("site_id", "") == record.get("site_id", "") and other["state"] == "active":
                    other["state"] = "retired"
                    other["updated_at"] = _now()
                    self._record_history(other["model_id"], "auto-retired-on-activation", "retired", model_id, actor)
        record["state"] = target_state
        record["updated_at"] = _now()
        self._record_history(model_id, reason, target_state, "", actor)
        self._persist()
        return dict(record)

    def rollback(self, model_id: str, *, reason: str, actor: str = "operator") -> dict[str, Any]:
        record = self._require(model_id)
        if record["state"] != "active":
            raise ModelLifecycleError("only an active model can be rolled back")
        candidates = [
            item for item in self._models.values()
            if item["model_name"] == record["model_name"] and item.get("site_id", "") == record.get("site_id", "") and item["state"] in {"approved", "retired"} and item["model_id"] != model_id
        ]
        if not candidates:
            raise ModelLifecycleError("no approved or retired rollback target is available")
        target = max(candidates, key=lambda item: item.get("updated_at", ""))
        record["state"] = "retired"
        target["state"] = "active"
        record["updated_at"] = target["updated_at"] = _now()
        self._record_history(model_id, reason, "retired", target["model_id"], actor)
        self._record_history(target["model_id"], "rollback-target", "active", model_id, actor)
        self._persist()
        return dict(target)

    def get(self, model_id: str) -> dict[str, Any] | None:
        record = self._models.get(model_id)
        return dict(record) if record else None

    def list(self, *, model_name: str | None = None, site_id: str | None = None) -> list[dict[str, Any]]:
        values = self._models.values()
        if model_name is not None:
            values = [item for item in values if item["model_name"] == model_name]
        if site_id is not None:
            values = [item for item in values if item.get("site_id", "") == site_id]
        return [dict(item) for item in sorted(values, key=lambda item: (item["model_name"], item["version"]))]

    def history(self, model_id: str | None = None) -> list[dict[str, Any]]:
        return [dict(item) for item in self._history if model_id is None or item["model_id"] == model_id]

    def _require(self, model_id: str) -> dict[str, Any]:
        record = self._models.get(model_id)
        if not record:
            raise ModelLifecycleError(f"unknown model version: {model_id}")
        return record

    def _record_history(self, model_id: str, action: str, state: str, related_id: str, actor: str) -> None:
        self._history.append({"model_id": model_id, "action": action, "state": state, "related_id": related_id, "actor": actor, "created_at": _now()})

    def _load(self) -> None:
        if not self._state_path or not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._models = {str(item["model_id"]): item for item in payload.get("models", [])}
        self._history = list(payload.get("history", []))

    def _persist(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"models": list(self._models.values()), "history": self._history}, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)

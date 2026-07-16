from __future__ import annotations

import json

import pytest

from services.common.model_lifecycle import ModelLifecycleError, ModelLifecycleLedger


def test_model_lifecycle_requires_evaluation_before_activation(tmp_path):
    path = tmp_path / "model-lifecycle.json"
    ledger = ModelLifecycleLedger(path)
    ledger.register(
        model_name="pump-world-model",
        version="2026.07.16.1",
        provider="local",
        model_type="dreamer",
        artifact_uri="s3://lakehouse/models/pump/1",
        dataset_id="company-pilot-v3",
        manifest_hash="abc123",
        site_id="plant-a",
    )

    with pytest.raises(ModelLifecycleError, match="passing evaluation"):
        ledger.transition("pump-world-model:2026.07.16.1", "approved", reason="try early")

    ledger.evaluate(
        "pump-world-model:2026.07.16.1",
        dataset_id="company-pilot-v3",
        metrics={"validation_loss": 0.12},
        passed=True,
        evaluator="offline-gate",
    )
    ledger.transition("pump-world-model:2026.07.16.1", "approved", reason="quality gate passed")
    active = ledger.transition("pump-world-model:2026.07.16.1", "active", reason="operator activation", actor="operator-1")

    assert active["state"] == "active"
    assert len(ledger.history("pump-world-model:2026.07.16.1")) == 4
    assert json.loads(path.read_text(encoding="utf-8"))["models"][0]["state"] == "active"


def test_activation_retires_previous_version_and_rollback_restores_it(tmp_path):
    ledger = ModelLifecycleLedger(tmp_path / "ledger.json")
    for version in ("1", "2"):
        model_id = f"pump:{version}"
        ledger.register(model_name="pump", version=version, provider="local", site_id="plant-a")
        ledger.evaluate(model_id, dataset_id="dataset", metrics={"loss": 0.2}, passed=True)
        ledger.transition(model_id, "approved", reason="approved")
    ledger.transition("pump:1", "active", reason="first active")
    ledger.transition("pump:1", "retired", reason="replace")
    ledger.transition("pump:2", "active", reason="new active")

    current = ledger.rollback("pump:2", reason="regression rollback", actor="operator-2")

    assert current["model_id"] == "pump:1"
    assert ledger.get("pump:2")["state"] == "retired"
    assert ledger.get("pump:1")["state"] == "active"


def test_invalid_transition_is_rejected(tmp_path):
    ledger = ModelLifecycleLedger(tmp_path / "ledger.json")
    ledger.register(model_name="model", version="1", provider="local")
    with pytest.raises(ModelLifecycleError, match="invalid model transition"):
        ledger.transition("model:1", "active", reason="unsafe")

from __future__ import annotations

from types import SimpleNamespace

from services.common import threshold_policy
from services.common.threshold_policy import evaluate_threshold, invalidate_policy_cache, resolve_threshold_policy, transition_threshold_state, validate_policy


def test_outside_range_policy_prioritizes_critical_over_warning() -> None:
    policy = validate_policy(
        {
            "mode": "outside_range",
            "warning_low": 10,
            "warning_high": 80,
            "critical_low": 0,
            "critical_high": 100,
            "enabled": True,
        }
    )
    assert evaluate_threshold(85, policy)["severity"] == "warning"
    assert evaluate_threshold(105, policy)["severity"] == "critical"
    assert evaluate_threshold(50, policy)["severity"] == "normal"


def test_directional_and_quality_policies_are_supported() -> None:
    assert evaluate_threshold(
        81,
        validate_policy({"mode": "above", "warning_high": 80, "critical_high": 100, "enabled": True}),
    )["severity"] == "warning"
    assert evaluate_threshold(
        1,
        validate_policy({"mode": "bad_quality", "enabled": True}),
        quality="bad",
    )["severity"] == "critical"


def test_invalid_policy_is_rejected() -> None:
    try:
        validate_policy({"mode": "outside_range", "warning_low": 10, "warning_high": 1})
    except ValueError as exc:
        assert "warning_low" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid range was accepted")


def test_transition_state_honors_on_delay_and_clears_after_off_delay() -> None:
    policy = validate_policy({"mode": "above", "warning_high": 80, "critical_high": 100, "on_delay_seconds": 5, "off_delay_seconds": 3, "enabled": True})
    first, candidate, since = transition_threshold_state("normal", None, 85, policy, now=100)
    assert first["severity"] == "normal"
    assert candidate == "warning"
    second, candidate, since = transition_threshold_state("normal", since, 85, policy, now=106)
    assert second["severity"] == "warning"
    assert candidate is None
    third, candidate, since = transition_threshold_state("warning", None, 50, policy, now=106)
    assert third["severity"] == "warning"
    assert candidate == "normal"
    fourth, _, _ = transition_threshold_state("warning", since, 50, policy, now=110)
    assert fourth["severity"] == "normal"


def test_manifest_policy_resolution_is_cached(monkeypatch, tmp_path) -> None:
    asset_file = tmp_path / "assets.yaml"
    asset_file.write_text("assets", encoding="utf-8")
    metadata = SimpleNamespace(
        name="temperature",
        unit="c",
        warning_low=None,
        warning_high=80,
        critical_low=None,
        critical_high=100,
    )
    hierarchy = SimpleNamespace(
        sites={
            "site-01": SimpleNamespace(
                areas={
                    "area": SimpleNamespace(
                        lines={
                            "line": SimpleNamespace(
                                cells={
                                    "cell": SimpleNamespace(
                                        assets={"Pump-01": SimpleNamespace(tags={"temperature": metadata})}
                                    )
                                }
                            )
                        }
                    )
                }
            )
        }
    )
    calls = 0

    def load(_path):
        nonlocal calls
        calls += 1
        return hierarchy

    monkeypatch.setattr(threshold_policy, "load_hierarchy", load)
    invalidate_policy_cache()
    first = resolve_threshold_policy("site-01", "Pump-01", "temperature", asset_config=str(asset_file))
    second = resolve_threshold_policy("site-01", "Pump-01", "temperature", asset_config=str(asset_file))

    assert first["source"] == "manifest"
    assert second["warning_high"] == 80
    assert calls == 1

import pytest
from pydantic import ValidationError

from services.common.ai_reporting import AIReportingPolicy, default_policy


def test_reporting_defaults_are_safe_for_local_and_air_gapped_deployments():
    policy = default_policy()
    assert policy.scheduled_interval_seconds == 3600
    assert policy.anomaly_enabled is False
    assert policy.recovery_enabled is True
    assert policy.anomaly_duration_seconds == 20
    assert policy.anomaly_severity == "critical"
    assert policy.exclude_replay is True


@pytest.mark.parametrize("seconds", [599, 86401])
def test_reporting_interval_has_operational_bounds(seconds):
    with pytest.raises(ValidationError):
        AIReportingPolicy(scheduled_interval_seconds=seconds)


def test_anomaly_policy_rejects_unbounded_or_unsupported_values():
    with pytest.raises(ValidationError):
        AIReportingPolicy(anomaly_duration_seconds=19)
    with pytest.raises(ValidationError):
        AIReportingPolicy(anomaly_severity="normal")

from services.benchmarks.live_soak_accounting import (
    account_pipeline,
    counter_delta,
    drain_passed,
    percentile,
)


def test_percentile_is_deterministic_and_handles_empty_input() -> None:
    assert percentile([], 95) is None
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([7], 99) == 7


def test_counter_delta_treats_reset_as_new_counter() -> None:
    assert counter_delta(10, 15) == 5
    assert counter_delta(15, 2) == 2


def test_pipeline_accounting_rejects_unexplained_events_and_duplicates() -> None:
    result = account_pipeline(
        attempted=100,
        acknowledged=100,
        historian_delta=100,
        processed_delta=100,
        ai_delta=20,
        dlq_delta=0,
    )
    assert result["passed"] is True

    failed = account_pipeline(
        attempted=100,
        acknowledged=100,
        historian_delta=99,
        processed_delta=100,
        ai_delta=20,
        dlq_delta=0,
        duplicate_delta=1,
    )
    assert failed["unexplained"] == 1
    assert failed["passed"] is False


def test_drain_requires_consecutive_zero_samples() -> None:
    assert drain_passed([4, 1, 0, 0, 0]) is True
    assert drain_passed([0, 0]) is False
    assert drain_passed([0, 0, 1, 0, 0]) is False

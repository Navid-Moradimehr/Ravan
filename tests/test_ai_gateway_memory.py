from services.ai_gateway.main import _append_bounded_evidence


def test_scheduled_report_evidence_window_is_bounded() -> None:
    batch = []
    for offset in range(10_000):
        _append_bounded_evidence(
            batch,
            ("iot.processed", 0, offset, {"event_id": str(offset)}),
            max_events=100,
        )

    assert len(batch) == 100
    assert batch[0][2] == 9_900
    assert batch[-1][2] == 9_999

from __future__ import annotations

import json


def test_delivery_ledger_redacts_destination_and_persists(tmp_path, monkeypatch):
    from services.api_service import delivery_ledger

    path = tmp_path / "delivery.json"
    monkeypatch.setattr(delivery_ledger, "LEDGER_PATH", path)
    delivery_ledger.record_delivery(
        channel="https://token:secret@example.test/hooks/a?key=hidden",
        kind="webhook",
        ok=False,
        attempts=3,
        status=503,
        error="temporary failure",
    )
    payload = json.loads(path.read_text())
    assert payload[0]["channel"] == "https://example.test"
    assert "secret" not in path.read_text()
    assert payload[0]["status"] == "failed"


def test_delivery_ledger_is_bounded(tmp_path, monkeypatch):
    from services.api_service import delivery_ledger

    monkeypatch.setattr(delivery_ledger, "LEDGER_PATH", tmp_path / "delivery.json")
    monkeypatch.setattr(delivery_ledger, "MAX_RECORDS", 2)
    for _ in range(3):
        delivery_ledger.record_delivery(channel="local://log", kind="apprise", ok=True)
    assert len(delivery_ledger.recent_deliveries()) == 2

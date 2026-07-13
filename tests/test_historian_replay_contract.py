from __future__ import annotations

from fastapi.testclient import TestClient


def test_historian_replay_contract_exposes_status_cycle(monkeypatch):
    import services.api_service.main as api_main
    import services.api_service.replay_state as replay_state

    # The API contract test must not require Kafka. The live worker is covered
    # by the Docker-backed replay smoke test.
    monkeypatch.setattr(replay_state, "_run_replay", lambda *args: None)

    replay_state.reset_replay_state()
    client = TestClient(api_main.app)

    response = client.get("/api/v1/historian/replay")
    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is False
    assert payload["dataset"] == "mock"
    assert payload["scenario"] == "normal"

    response = client.post("/api/v1/historian/replay", json={"dataset": "mock", "scenario": "normal"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["replay"]["running"] is True
    assert payload["replay"]["dataset"] == "mock"
    assert payload["replay"]["scenario"] == "normal"

    response = client.get("/api/v1/historian/replay")
    assert response.status_code == 200
    payload = response.json()
    assert payload["running"] is True
    assert payload["progress_percent"] >= 0
    assert payload["events_emitted"] >= 0

    response = client.delete("/api/v1/historian/replay")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["replay"]["running"] is False
    assert payload["replay"]["status"] == "stopped"


def test_historian_replay_rejects_unknown_dataset():
    import services.api_service.main as api_main
    from services.api_service.replay_state import reset_replay_state

    reset_replay_state()
    client = TestClient(api_main.app)

    response = client.post("/api/v1/historian/replay", json={"dataset": "does-not-exist", "scenario": "normal"})
    assert response.status_code == 400
    assert "Unknown dataset" in response.json()["detail"]

from __future__ import annotations

from fastapi.testclient import TestClient


def test_historian_replay_rejects_unknown_dataset():
    import services.api_service.main as api_main
    from services.api_service.replay_state import reset_replay_state

    reset_replay_state()
    client = TestClient(api_main.app)

    response = client.post("/api/v1/historian/replay", json={"dataset": "does-not-exist", "scenario": "normal"})
    assert response.status_code == 400
    assert "Unknown dataset" in response.json()["detail"]

from __future__ import annotations

from fastapi.testclient import TestClient

from services.api_service.main import app


def test_mutating_route_requires_bearer_token(monkeypatch):
    import services.api_service.main as api_main

    monkeypatch.setattr(api_main, "_persist_webhooks", lambda: None)
    client = TestClient(app)

    response = client.post(
        "/api/v1/webhooks",
        json={"url": "http://example.com/hook"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_mutating_route_accepts_valid_bearer_token(monkeypatch):
    import services.api_service.main as api_main
    from services.api_service.auth import create_access_token

    monkeypatch.setattr(api_main, "_persist_webhooks", lambda: None)
    client = TestClient(app)
    token = create_access_token("user-1", "operator")

    response = client.post(
        "/api/v1/webhooks",
        json={"url": "http://example.com/hook"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "registered"


def test_health_exposes_security_headers():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

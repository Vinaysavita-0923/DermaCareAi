"""Tests for Phase 1: the root and health endpoints.

These are intentionally simple — Phase 1 has no database, no auth, and
no external services, so there is nothing to mock yet.
"""
from fastapi.testclient import TestClient

from app.main import app, settings

client = TestClient(app)


def test_root_returns_service_info():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == settings.app_name
    assert body["api_prefix"] == "/api/v1"


def test_health_endpoint_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "environment" in body


def test_unknown_route_returns_404():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404


def test_health_endpoint_is_get_only():
    # POST should not be implicitly accepted by a GET-only route.
    response = client.post("/api/v1/health")
    assert response.status_code == 405

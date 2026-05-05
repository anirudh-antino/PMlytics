"""Minimal smoke tests — import app and hit one read-only endpoint."""

from fastapi.testclient import TestClient

from app import app


def test_api_status() -> None:
    with TestClient(app) as client:
        r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "connection_count" in data
    assert data["connection_count"] == 0

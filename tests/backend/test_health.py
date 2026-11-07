"""
Automated unit tests for Health and Root endpoints.
"""
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "KitchenVerse"
    assert "message" in data
    assert "/api/v1" in data["api_v1"]


def test_health_check_endpoint(client: TestClient):
    # Verify primary API health endpoint
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "KitchenVerse"
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

    # Verify root health alias for load balancers
    alias_response = client.get("/health")
    assert alias_response.status_code == 200
    alias_data = alias_response.json()
    assert alias_data["status"] == "healthy"
    assert alias_data["database"] == "connected"

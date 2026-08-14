"""Unit and Integration tests for root service and health check endpoints."""

from fastapi.testclient import TestClient


def test_get_root_service_status(client: TestClient) -> None:
    """Test GET / returns expected service status payload."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Email Enrichment Tool"
    assert data["status"] == "running"


def test_get_health_status(client: TestClient) -> None:
    """Test GET /health returns expected system health status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data

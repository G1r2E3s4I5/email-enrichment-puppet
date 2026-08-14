"""Comprehensive resiliency, fault tolerance, DB outage fallback, and health check tests."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.retry import execute_with_retry
from app.providers.brandfetch_provider import BrandfetchDomainProvider

client = TestClient(app)


def test_job_upload_with_db_dns_failure():
    """Test POST /api/v1/jobs/upload succeeds with HTTP 201 via memory fallback when DB throws getaddrinfo failed error."""
    file_content = "Company,First Name,Last Name\nStripe,John,Doe\n"
    files = {"file": ("test_resiliency.csv", file_content.encode("utf-8"), "text/csv")}

    with patch("app.database.repositories.job_repository.get_supabase_client", side_effect=Exception("[Errno 11001] getaddrinfo failed")):
        response = client.post("/api/v1/jobs/upload", files=files)
        assert response.status_code == 201
        data = response.json()
        assert "job_id" in data
        assert data["rows"] == 1


@pytest.mark.asyncio
async def test_brandfetch_placeholder_validation_triggering_fallback():
    """Test Brandfetch rejects placeholder domain responses like 'none' or 'example.com' and returns success=False."""
    provider = BrandfetchDomainProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"domain": "example.com"}

    with patch.object(provider, "_execute_http_request", return_value=mock_resp):
        res = await provider.resolve_domain("TestCompany")
        assert res.success is False
        assert res.domain is None
        assert "placeholder" in res.error.lower()


def test_health_monitoring_endpoints():
    """Test GET /health, /health/database, /health/cache, and /health/providers endpoints."""
    res_root = client.get("/health")
    assert res_root.status_code == 200
    assert "status" in res_root.json()

    res_db = client.get("/health/database")
    assert res_db.status_code == 200
    assert "connected" in res_db.json()

    res_cache = client.get("/health/cache")
    assert res_cache.status_code == 200
    assert "redis_connected" in res_cache.json()

    res_providers = client.get("/health/providers")
    assert res_providers.status_code == 200
    assert "providers" in res_providers.json()


def test_retry_utility_exponential_backoff():
    """Test execute_with_retry utility retries transient errors with exponential backoff."""
    counter = {"attempts": 0}

    def flaky_func():
        counter["attempts"] += 1
        if counter["attempts"] < 3:
            raise ValueError("Transient error")
        return "success"

    result = execute_with_retry(flaky_func, max_attempts=3, backoff_base=0.01, jitter=False)
    assert result == "success"
    assert counter["attempts"] == 3

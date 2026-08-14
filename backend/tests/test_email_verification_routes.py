"""Integration tests for Email Verification REST API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies.services import get_email_verification_service
from app.schemas.email_verification import (
    EmailVerificationResponse,
    VerificationProviderHealthResponse,
)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_verification_service():
    service = MagicMock()
    service.get_active_provider_name.return_value = "Mock"
    service.get_supported_providers.return_value = ["mock", "hunter", "zerobounce", "neverbounce", "abstract"]

    ver_res = EmailVerificationResponse(
        email="john@stripe.com",
        status="valid",
        confidence=96.0,
        is_disposable=False,
        is_role_account=False,
        is_catch_all=False,
        provider="Mock",
    )
    service.verify_email = AsyncMock(return_value=ver_res)

    health_res = VerificationProviderHealthResponse(
        provider="Mock",
        status="healthy",
        connected=True,
    )
    service.get_active_provider_health = AsyncMock(return_value=health_res)
    return service


def test_verify_email_endpoint_success(test_client: TestClient, mock_verification_service):
    app.dependency_overrides[get_email_verification_service] = lambda: mock_verification_service
    try:
        response = test_client.post(
            "/api/v1/email/verify",
            json={"email": "john@stripe.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "john@stripe.com"
        assert data["status"] == "valid"
        assert data["confidence"] == 96.0
        assert data["provider"] == "Mock"
    finally:
        app.dependency_overrides.clear()


def test_get_verification_providers_endpoint(test_client: TestClient, mock_verification_service):
    app.dependency_overrides[get_email_verification_service] = lambda: mock_verification_service
    try:
        response = test_client.get("/api/v1/email/providers")
        assert response.status_code == 200
        data = response.json()
        assert data["active_provider"] == "Mock"
        assert "mock" in data["supported_providers"]
    finally:
        app.dependency_overrides.clear()


def test_get_verification_provider_health_endpoint(test_client: TestClient, mock_verification_service):
    app.dependency_overrides[get_email_verification_service] = lambda: mock_verification_service
    try:
        response = test_client.get("/api/v1/email/providers/health")
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "Mock"
        assert data["status"] == "healthy"
        assert data["connected"] is True
    finally:
        app.dependency_overrides.clear()

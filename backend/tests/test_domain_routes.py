"""Integration tests for production Domain Resolution API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies.services import get_domain_resolver_service
from app.schemas.domain_resolver import ResolverDomainResult

client = TestClient(app)


def test_resolve_domain_cache_hit() -> None:
    """Test POST /api/v1/domain/resolve cache hit returning cached domain."""
    mock_result = ResolverDomainResult(
        success=True,
        company="Stripe",
        domain="stripe.com",
        provider="Cache",
        cached=True,
        confidence=1.0,
        error=None,
    )

    mock_service = MagicMock()
    mock_service.resolve_domain = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_domain_resolver_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/domain/resolve",
            json={"company": "Stripe"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["company"] == "Stripe"
        assert data["domain"] == "stripe.com"
        assert data["provider"] == "Cache"
        assert data["cached"] is True
    finally:
        app.dependency_overrides.clear()


def test_resolve_domain_brandfetch_success() -> None:
    """Test POST /api/v1/domain/resolve returning Brandfetch resolved domain."""
    mock_result = ResolverDomainResult(
        success=True,
        company="Stripe",
        domain="stripe.com",
        provider="Brandfetch",
        cached=False,
        confidence=1.0,
        error=None,
    )

    mock_service = MagicMock()
    mock_service.resolve_domain = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_domain_resolver_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/domain/resolve",
            json={"company": "Stripe"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "Brandfetch"
        assert data["cached"] is False
    finally:
        app.dependency_overrides.clear()


def test_resolve_domain_serpapi_fallback() -> None:
    """Test POST /api/v1/domain/resolve returning SerpAPI fallback domain."""
    mock_result = ResolverDomainResult(
        success=True,
        company="OpenAI",
        domain="openai.com",
        provider="SerpAPI",
        cached=False,
        confidence=0.95,
        error=None,
    )

    mock_service = MagicMock()
    mock_service.resolve_domain = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_domain_resolver_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/domain/resolve",
            json={"company": "OpenAI"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "SerpAPI"
    finally:
        app.dependency_overrides.clear()


def test_resolve_domain_unknown_company() -> None:
    """Test POST /api/v1/domain/resolve returning failure payload when resolution fails."""
    mock_result = ResolverDomainResult(
        success=False,
        company="UnknownCompany123",
        domain=None,
        provider=None,
        cached=False,
        confidence=0.0,
        error="Company not found",
    )

    mock_service = MagicMock()
    mock_service.resolve_domain = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_domain_resolver_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/domain/resolve",
            json={"company": "UnknownCompany123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["domain"] is None
        assert data["error"] == "Company not found"
    finally:
        app.dependency_overrides.clear()


def test_resolve_domain_validation_empty_string() -> None:
    """Test POST /api/v1/domain/resolve validation failure on empty string."""
    response = client.post(
        "/api/v1/domain/resolve",
        json={"company": ""},
    )
    assert response.status_code == 422


def test_batch_preview_success() -> None:
    """Test POST /api/v1/domain/resolve/batch-preview with valid list of companies."""
    mock_result_1 = ResolverDomainResult(
        success=True, company="Stripe", domain="stripe.com", provider="Brandfetch", cached=False, confidence=1.0
    )
    mock_result_2 = ResolverDomainResult(
        success=True, company="OpenAI", domain="openai.com", provider="SerpAPI", cached=False, confidence=0.95
    )

    mock_service = MagicMock()
    mock_service.resolve_domain = AsyncMock(side_effect=[mock_result_1, mock_result_2])

    app.dependency_overrides[get_domain_resolver_service] = lambda: mock_service
    try:
        response = client.post(
            "/api/v1/domain/resolve/batch-preview",
            json={"companies": ["Stripe", "OpenAI"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["successful"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2
        assert data["results"][0]["domain"] == "stripe.com"
        assert data["results"][1]["domain"] == "openai.com"
    finally:
        app.dependency_overrides.clear()


def test_batch_preview_validation_limit_exceeded() -> None:
    """Test POST /api/v1/domain/resolve/batch-preview validation failure when exceeding 10 companies."""
    companies = [f"Company{i}" for i in range(11)]
    response = client.post(
        "/api/v1/domain/resolve/batch-preview",
        json={"companies": companies},
    )
    assert response.status_code == 422

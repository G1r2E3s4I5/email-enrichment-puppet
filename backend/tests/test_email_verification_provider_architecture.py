"""Comprehensive unit and integration tests for Phase 4.3 Email Verification Provider Architecture."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.mock_provider import MockProvider
from app.providers.email_verification.provider_registry import ProviderRegistry
from app.providers.email_verification.provider_factory import ProviderFactory
from app.services.verification_provider_service import VerificationProviderService
from app.services.email_verification_service import EmailVerificationService


client = TestClient(app)


class CustomTestProvider(EmailVerificationProvider):
    """Custom mock provider for testing provider registration."""

    def get_provider_name(self) -> str:
        return "custom_test"

    async def health_check(self):
        return {"name": "custom_test", "healthy": True}

    async def verify(self, email: str):
        return {
            "status": "valid",
            "confidence": 99.0,
            "provider": "custom_test",
            "is_disposable": False,
            "is_role_account": False,
            "is_catch_all": False,
            "mx_checked": True,
            "smtp_checked": True,
            "error": None,
        }


def test_provider_registry():
    """Test ProviderRegistry registration, lookup, and fallback behavior."""
    providers = ProviderRegistry.list_providers()
    assert "mock" in providers
    assert "neverbounce" in providers
    assert "zerobounce" in providers
    assert "hunter" in providers
    assert "abstract" in providers

    ProviderRegistry.register_provider("custom_test", CustomTestProvider)
    assert "custom_test" in ProviderRegistry.list_providers()
    assert ProviderRegistry.get_provider("custom_test") == CustomTestProvider

    # Unknown provider falls back to MockProvider
    assert ProviderRegistry.get_provider("unknown_provider_xyz") == MockProvider


def test_provider_factory():
    """Test ProviderFactory instantiates configured provider."""
    factory = ProviderFactory("mock")
    provider = factory.get_provider()
    assert isinstance(provider, MockProvider)
    assert provider.get_provider_name() == "Mock"

    factory_custom = ProviderFactory("custom_test")
    custom_prov = factory_custom.get_provider()
    assert isinstance(custom_prov, CustomTestProvider)
    assert custom_prov.get_provider_name() == "custom_test"


@pytest.mark.asyncio
async def test_mock_provider_verification_rules():
    """Test MockProvider deterministic verification output across syntax, disposable, role, catch-all, and valid cases."""
    provider = MockProvider()
    assert provider.get_provider_name() == "Mock"

    health = await provider.health_check()
    assert health["healthy"] is True
    assert health["name"] == "Mock"

    # Syntax error
    invalid_res = await provider.verify("not-an-email")
    assert invalid_res["status"] == "invalid"
    assert invalid_res["confidence"] == 0.0

    # Disposable domain
    disp_res = await provider.verify("user@mailinator.com")
    assert disp_res["status"] == "invalid"
    assert disp_res["is_disposable"] is True

    # Role account
    role_res = await provider.verify("admin@company.com")
    assert role_res["status"] == "valid"
    assert role_res["is_role_account"] is True

    # Catch-all
    catch_res = await provider.verify("user@catchall.com")
    assert catch_res["status"] == "catch_all"
    assert catch_res["is_catch_all"] is True

    # Standard valid
    valid_res = await provider.verify("john.doe@stripe.com")
    assert valid_res["status"] == "valid"
    assert valid_res["confidence"] == 96.0


@pytest.mark.asyncio
async def test_verification_provider_service():
    """Test VerificationProviderService delegating to active provider and normalizing output."""
    service = VerificationProviderService(provider=MockProvider())
    assert service.get_active_provider_name() == "Mock"

    response = await service.verify_email("john.doe@stripe.com")
    assert response.email == "john.doe@stripe.com"
    assert response.status == "valid"
    assert response.confidence == 96.0
    assert response.provider == "Mock"

    meta = await service.get_providers_metadata()
    assert meta["active_provider"] == "Mock"
    assert "mock" in meta["available_providers"]
    assert meta["provider_status"]["healthy"] is True


def test_api_get_email_verification_providers_endpoint():
    """Test GET /api/v1/email-verification/providers REST API endpoint."""
    response = client.get("/api/v1/email-verification/providers")
    assert response.status_code == 200
    data = response.json()
    assert "active_provider" in data
    assert "available_providers" in data
    assert "provider_status" in data

    assert data["active_provider"] in ("Mock", "Composite")
    assert "mock" in data["available_providers"]
    assert "neverbounce" in data["available_providers"]
    assert "zerobounce" in data["available_providers"]
    assert "hunter" in data["available_providers"]
    assert "abstract" in data["available_providers"]


def test_api_post_email_verify_endpoint_compatibility():
    """Test POST /api/v1/email/verify REST API endpoint compatibility."""
    with patch("app.config.settings.settings.EMAIL_VERIFICATION_PROVIDER", "mock"):
        response = client.post(
            "/api/v1/email/verify",
            json={"email": "john.smith@stripe.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "john.smith@stripe.com"
        assert data["status"] in ("valid", "risky")
        assert data["provider"] in ("Mock", "Composite")


@pytest.mark.asyncio
async def test_provider_switching_via_environment():
    """Test switching active provider via environment configuration."""
    with patch("app.config.settings.settings.EMAIL_VERIFICATION_PROVIDER", "neverbounce"):
        factory = ProviderFactory()
        provider = factory.get_provider()
        assert provider.get_provider_name() == "Mock"  # neverbounce falls back to MockProvider stub

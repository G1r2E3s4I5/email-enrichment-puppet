"""Unit tests for EmailVerificationService layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.schemas.email_verification import EmailVerificationResponse
from app.services.email_verification_service import EmailVerificationService


@pytest.fixture
def mock_provider_fixture():
    provider = MagicMock()
    provider.get_provider_name.return_value = "TestProvider"
    provider.health_check = AsyncMock(return_value={"status": "healthy", "provider": "TestProvider", "connected": True})

    ver_res = EmailVerificationResponse(
        email="test@example.com",
        status="valid",
        confidence=95.0,
        is_disposable=False,
        is_role_account=False,
        is_catch_all=False,
        provider="TestProvider",
    )
    provider.verify_email = AsyncMock(return_value=ver_res)
    return provider


@pytest.mark.asyncio
async def test_service_verify_email_delegation(mock_provider_fixture):
    service = EmailVerificationService(provider=mock_provider_fixture)
    assert service.get_active_provider_name() == "TestProvider"

    result = await service.verify_email("test@example.com")
    assert result.status == "valid"
    assert result.provider == "TestProvider"
    mock_provider_fixture.verify_email.assert_called_once_with("test@example.com")


@pytest.mark.asyncio
async def test_service_health_check_delegation(mock_provider_fixture):
    service = EmailVerificationService(provider=mock_provider_fixture)
    health = await service.get_active_provider_health()

    assert health.provider == "TestProvider"
    assert health.status == "healthy"
    assert health.connected is True
    mock_provider_fixture.health_check.assert_called_once()

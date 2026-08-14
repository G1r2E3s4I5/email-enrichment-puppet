"""Unit tests for MockProvider email verification implementation."""

import pytest
from app.providers.email_verification.mock_provider import MockProvider
from app.schemas.email_verification import EmailVerificationResponse


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


def test_provider_name(mock_provider: MockProvider):
    assert mock_provider.get_provider_name() in ("Mock", "MockVerification")


@pytest.mark.asyncio
async def test_health_check(mock_provider: MockProvider):
    health = await mock_provider.health_check()
    assert health["healthy"] is True


@pytest.mark.asyncio
async def test_verify_deliverable_email(mock_provider: MockProvider):
    res = await mock_provider.verify("john@stripe.com")
    assert isinstance(res, dict) or isinstance(res, EmailVerificationResponse)
    status_val = res["status"] if isinstance(res, dict) else res.status
    assert status_val == "valid"


@pytest.mark.asyncio
async def test_verify_disposable_email(mock_provider: MockProvider):
    res = await mock_provider.verify("user@mailinator.com")
    is_disp = res.get("is_disposable") if isinstance(res, dict) else res.is_disposable
    assert is_disp is True


@pytest.mark.asyncio
async def test_verify_role_account_email(mock_provider: MockProvider):
    res = await mock_provider.verify("admin@company.com")
    is_role = res.get("is_role_account") if isinstance(res, dict) else res.is_role_account
    assert is_role is True


@pytest.mark.asyncio
async def test_verify_catch_all_email(mock_provider: MockProvider):
    res = await mock_provider.verify("alex@catchall.com")
    status_val = res.get("status") if isinstance(res, dict) else res.status
    assert status_val in ("catch_all", "valid")


@pytest.mark.asyncio
async def test_verify_invalid_syntax_email(mock_provider: MockProvider):
    res = await mock_provider.verify("invalid-email-string")
    status_val = res.get("status") if isinstance(res, dict) else res.status
    assert status_val == "invalid"

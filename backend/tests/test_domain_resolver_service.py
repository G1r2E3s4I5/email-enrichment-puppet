"""Unit tests for DomainResolverService orchestration logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from uuid import uuid4

from app.core.exceptions import DatabaseException
from app.schemas.company_domain import CompanyDomainResponse
from app.schemas.domain_provider import DomainResolutionResult
from app.schemas.domain_resolver import ResolverDomainResult
from app.services.domain_resolver_service import DomainResolverService


@pytest.fixture
def mock_company_repo() -> MagicMock:
    """Fixture providing a mocked CompanyDomainRepository."""
    return MagicMock()


@pytest.fixture
def mock_audit_repo() -> MagicMock:
    """Fixture providing a mocked DomainResolutionLogRepository."""
    return MagicMock()


@pytest.fixture
def mock_brandfetch_provider() -> MagicMock:
    """Fixture providing a mocked BrandfetchDomainProvider."""
    provider = MagicMock()
    provider.resolve_domain = AsyncMock()
    return provider


@pytest.fixture
def mock_serpapi_provider() -> MagicMock:
    """Fixture providing a mocked SerpApiDomainProvider."""
    provider = MagicMock()
    provider.resolve_domain = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_resolver_cache_hit(
    mock_company_repo: MagicMock,
    mock_audit_repo: MagicMock,
    mock_brandfetch_provider: MagicMock,
    mock_serpapi_provider: MagicMock,
) -> None:
    """Test resolution returning immediately from cache on cache hit."""
    cached_entry = CompanyDomainResponse(
        id=uuid4(),
        company_name="Stripe",
        normalized_name="stripe",
        domain="stripe.com",
        provider="Brandfetch",
        confidence=1.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_company_repo.get_by_normalized_name.return_value = cached_entry

    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        audit_log_repo=mock_audit_repo,
        brandfetch_provider=mock_brandfetch_provider,
        serpapi_provider=mock_serpapi_provider,
    )

    result = await service.resolve_domain(" Stripe ")

    assert isinstance(result, ResolverDomainResult)
    assert result.success is True
    assert result.domain == "stripe.com"
    assert result.provider == "Cache"
    assert result.cached is True

    # Verify providers were NEVER called
    mock_brandfetch_provider.resolve_domain.assert_not_called()
    mock_serpapi_provider.resolve_domain.assert_not_called()

    # Verify audit log was recorded
    mock_audit_repo.insert_log.assert_called_once()
    log_arg = mock_audit_repo.insert_log.call_args[0][0]
    assert log_arg.provider == "Cache"
    assert log_arg.cached is True


@pytest.mark.asyncio
async def test_resolver_cache_miss_brandfetch_success(
    mock_company_repo: MagicMock,
    mock_audit_repo: MagicMock,
    mock_brandfetch_provider: MagicMock,
    mock_serpapi_provider: MagicMock,
) -> None:
    """Test cache miss proceeding to Brandfetch and persisting to cache on success."""
    mock_company_repo.get_by_normalized_name.return_value = None
    mock_brandfetch_provider.resolve_domain.return_value = DomainResolutionResult(
        success=True,
        company="Stripe",
        domain="stripe.com",
        provider="Brandfetch",
        confidence=1.0,
    )

    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        audit_log_repo=mock_audit_repo,
        brandfetch_provider=mock_brandfetch_provider,
        serpapi_provider=mock_serpapi_provider,
    )

    result = await service.resolve_domain("Stripe")

    assert result.success is True
    assert result.domain == "stripe.com"
    assert result.provider == "Brandfetch"
    assert result.cached is False

    mock_brandfetch_provider.resolve_domain.assert_called_once_with("Stripe")
    mock_serpapi_provider.resolve_domain.assert_not_called()
    mock_company_repo.insert_cache.assert_called_once()
    mock_audit_repo.insert_log.assert_called_once()


@pytest.mark.asyncio
async def test_resolver_brandfetch_fails_serpapi_success(
    mock_company_repo: MagicMock,
    mock_audit_repo: MagicMock,
    mock_brandfetch_provider: MagicMock,
    mock_serpapi_provider: MagicMock,
) -> None:
    """Test Brandfetch failure falling back to SerpAPI and persisting result."""
    mock_company_repo.get_by_normalized_name.return_value = None
    mock_brandfetch_provider.resolve_domain.return_value = DomainResolutionResult(
        success=False,
        company="OpenAI",
        domain=None,
        provider="Brandfetch",
        error="Company not found",
    )
    mock_serpapi_provider.resolve_domain.return_value = DomainResolutionResult(
        success=True,
        company="OpenAI",
        domain="openai.com",
        provider="SerpAPI",
        confidence=0.95,
    )

    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        audit_log_repo=mock_audit_repo,
        brandfetch_provider=mock_brandfetch_provider,
        serpapi_provider=mock_serpapi_provider,
    )

    result = await service.resolve_domain("OpenAI")

    assert result.success is True
    assert result.domain == "openai.com"
    assert result.provider == "SerpAPI"
    assert result.cached is False

    mock_brandfetch_provider.resolve_domain.assert_called_once_with("OpenAI")
    mock_serpapi_provider.resolve_domain.assert_called_once_with("OpenAI")
    mock_company_repo.insert_cache.assert_called_once()
    mock_audit_repo.insert_log.assert_called_once()


@pytest.mark.asyncio
async def test_resolver_both_providers_fail(
    mock_company_repo: MagicMock,
    mock_audit_repo: MagicMock,
    mock_brandfetch_provider: MagicMock,
    mock_serpapi_provider: MagicMock,
) -> None:
    """Test resolution returning failure payload when all providers fail."""
    mock_company_repo.get_by_normalized_name.return_value = None
    mock_brandfetch_provider.resolve_domain.return_value = DomainResolutionResult(
        success=False, company="Unknown", domain=None, provider="Brandfetch", error="Not found"
    )
    mock_serpapi_provider.resolve_domain.return_value = DomainResolutionResult(
        success=False, company="Unknown", domain=None, provider="SerpAPI", error="Not found"
    )

    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        audit_log_repo=mock_audit_repo,
        brandfetch_provider=mock_brandfetch_provider,
        serpapi_provider=mock_serpapi_provider,
    )

    result = await service.resolve_domain("Unknown")

    assert result.success is False
    assert result.domain is None
    assert result.provider is None
    assert result.error == "Company not found or rejected domain"

    mock_company_repo.insert_cache.assert_not_called()
    mock_audit_repo.insert_log.assert_called_once()
    log_arg = mock_audit_repo.insert_log.call_args[0][0]
    assert log_arg.status == "not_found"


@pytest.mark.asyncio
async def test_resolver_database_unavailable_graceful_handling(
    mock_company_repo: MagicMock,
    mock_audit_repo: MagicMock,
    mock_brandfetch_provider: MagicMock,
    mock_serpapi_provider: MagicMock,
) -> None:
    """Test DB failure on cache read/write does not crash service."""
    mock_company_repo.get_by_normalized_name.side_effect = DatabaseException("DB down")
    mock_company_repo.insert_cache.side_effect = DatabaseException("DB down")
    mock_audit_repo.insert_log.side_effect = DatabaseException("DB down")

    mock_brandfetch_provider.resolve_domain.return_value = DomainResolutionResult(
        success=True, company="Netflix", domain="netflix.com", provider="Brandfetch", confidence=1.0
    )

    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        audit_log_repo=mock_audit_repo,
        brandfetch_provider=mock_brandfetch_provider,
        serpapi_provider=mock_serpapi_provider,
    )

    result = await service.resolve_domain("Netflix")

    assert result.success is True
    assert result.domain == "netflix.com"
    assert result.provider == "Brandfetch"


@pytest.mark.asyncio
async def test_resolver_validation_error() -> None:
    """Test handling empty or whitespace company input."""
    service = DomainResolverService()

    res = await service.resolve_domain("   ")
    assert res.success is False
    assert res.error == "Company name must not be empty"

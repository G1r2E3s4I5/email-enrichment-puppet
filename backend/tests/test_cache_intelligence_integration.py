"""Integration tests for Domain Cache Intelligence, Statistics, and Refresh endpoints."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.schemas.company_domain import CompanyDomainResponse
from app.services.domain_resolver_service import DomainResolverService
from app.services.cache_statistics_service import CacheStatisticsService
from app.services.cache_validation_service import CacheValidationService


@pytest.fixture
def mock_company_repo():
    repo = MagicMock()
    repo.get_by_normalized_name.return_value = None
    repo.insert_cache.return_value = MagicMock(id="123", domain="openai.com", confidence=95.0)
    repo.update_cache.return_value = MagicMock(id="123", domain="openai.com", confidence=98.0)
    return repo


@pytest.fixture
def mock_brandfetch():
    provider = MagicMock()
    res = MagicMock()
    res.success = True
    res.domain = "openai.com"
    res.confidence = 90.0
    provider.resolve_domain = AsyncMock(return_value=res)
    return provider


@pytest.mark.asyncio
async def test_cache_hit_and_miss_logging(mock_company_repo, mock_brandfetch):
    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        brandfetch_provider=mock_brandfetch,
    )

    # First call: Cache Miss -> calls provider
    res1 = await service.resolve_domain("OpenAI")
    assert res1.success is True
    assert res1.cached is False
    assert res1.domain == "openai.com"

    stats = service.statistics_service.get_statistics()
    assert stats.cache_misses >= 1

    # Second call with mock returning cached item
    mock_company_repo.get_by_normalized_name.return_value = CompanyDomainResponse(
        id="12345678-1234-5678-1234-567812345678",
        company_name="OpenAI",
        normalized_name="openai",
        domain="openai.com",
        provider="Brandfetch",
        confidence=95.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    res2 = await service.resolve_domain("OpenAI")
    assert res2.success is True
    assert res2.cached is True

    stats2 = service.statistics_service.get_statistics()
    assert stats2.cache_hits >= 1


@pytest.mark.asyncio
async def test_rejected_suspicious_domain_not_cached(mock_company_repo):
    # Brandfetch returns suspicious domain for IBM (ibmadison.com)
    mock_bf = MagicMock()
    bf_res = MagicMock()
    bf_res.success = True
    bf_res.domain = "ibmadison.com"
    bf_res.confidence = 80.0
    mock_bf.resolve_domain = AsyncMock(return_value=bf_res)

    mock_serp = MagicMock()
    serp_res = MagicMock()
    serp_res.success = False
    serp_res.domain = None
    mock_serp.resolve_domain = AsyncMock(return_value=serp_res)

    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        brandfetch_provider=mock_bf,
        serpapi_provider=mock_serp,
    )

    res = await service.resolve_domain("IBM")
    assert res.success is False
    # Verify insert_cache was NEVER called for rejected domain!
    mock_company_repo.insert_cache.assert_not_called()


@pytest.mark.asyncio
async def test_cache_refresh_single(mock_company_repo, mock_brandfetch):
    service = DomainResolverService(
        company_domain_repo=mock_company_repo,
        brandfetch_provider=mock_brandfetch,
    )

    refresh_res = await service.refresh_company_cache("OpenAI")
    assert refresh_res.success is True
    assert refresh_res.company == "OpenAI"
    assert refresh_res.refreshed_count == 1

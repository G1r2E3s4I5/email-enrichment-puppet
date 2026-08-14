"""Comprehensive unit and integration tests for Phase 4.5 Parallel Domain Resolution Pipeline."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.schemas.domain_resolver import ResolverDomainResult
from app.services.domain_resolver_service import DomainResolverService


class ConcurrencyTrackingResolverService(DomainResolverService):
    """Custom service tracking active simultaneous domain resolution tasks."""

    def __init__(self, delay: float = 0.05):
        super().__init__()
        self.delay = delay
        self.active_concurrency = 0
        self.max_observed_concurrency = 0
        self.lock = asyncio.Lock()

    async def resolve_domain(self, company_name: str, force_refresh: bool = False) -> ResolverDomainResult:
        if company_name == "ErrorCorp":
            raise RuntimeError("Simulated provider failure for ErrorCorp")

        async with self.lock:
            self.active_concurrency += 1
            if self.active_concurrency > self.max_observed_concurrency:
                self.max_observed_concurrency = self.active_concurrency

        await asyncio.sleep(self.delay)

        async with self.lock:
            self.active_concurrency -= 1

        clean_name = company_name.lower().replace(" ", "").replace(".", "")
        return ResolverDomainResult(
            success=True,
            company=company_name,
            domain=f"{clean_name}.com",
            provider="MockProvider",
            cached=False,
            confidence=95.0,
            error=None,
        )


@pytest.mark.asyncio
async def test_concurrency_limit_respected():
    """Test that max concurrency limit (e.g. 5) is strictly respected by asyncio.Semaphore."""
    service = ConcurrencyTrackingResolverService(delay=0.08)
    companies = [f"Company {i}" for i in range(25)]

    results = await service.resolve_domains_batch(
        companies=companies,
        concurrency=5,
    )

    assert len(results) == 25
    assert service.max_observed_concurrency <= 5
    assert all(r.success for r in results)


@pytest.mark.asyncio
async def test_failure_isolation():
    """Test that an exception on one company does not stop processing for remaining companies."""
    service = ConcurrencyTrackingResolverService(delay=0.01)
    companies = ["Stripe", "ErrorCorp", "Google", "Microsoft"]

    results = await service.resolve_domains_batch(
        companies=companies,
        concurrency=2,
    )

    assert len(results) == 4

    assert results[0].company == "Stripe"
    assert results[0].success is True

    # ErrorCorp failed but was isolated
    assert results[1].company == "ErrorCorp"
    assert results[1].success is False
    assert "Simulated provider failure for ErrorCorp" in results[1].error

    assert results[2].company == "Google"
    assert results[2].success is True

    assert results[3].company == "Microsoft"
    assert results[3].success is True


@pytest.mark.asyncio
async def test_row_order_preservation():
    """Test that returned batch results strictly preserve the original CSV input order."""
    service = ConcurrencyTrackingResolverService(delay=0.02)
    companies = [f"Enterprise {i}" for i in range(30)]

    results = await service.resolve_domains_batch(
        companies=companies,
        concurrency=10,
    )

    assert len(results) == 30
    for idx, expected_company in enumerate(companies):
        assert results[idx].company == expected_company
        clean_name = expected_company.lower().replace(" ", "").replace(".", "")
        assert results[idx].domain == f"{clean_name}.com"


@pytest.mark.asyncio
async def test_cache_brandfetch_serpapi_fallback_integration():
    """Test parallel batch resolution with cache hit, Brandfetch, and SerpAPI fallback providers."""
    mock_repo = MagicMock()
    mock_repo.get_by_normalized_name.return_value = None  # Cache miss

    mock_brandfetch = MagicMock()
    mock_brandfetch.resolve_domain = AsyncMock(
        side_effect=lambda name: ResolverDomainResult(
            success=True if "brandfetch" in name.lower() else False,
            company=name,
            domain=f"{name.lower().replace(' ', '')}.com" if "brandfetch" in name.lower() else None,
            provider="Brandfetch",
            cached=False,
            confidence=90.0,
        )
    )

    mock_serpapi = MagicMock()
    mock_serpapi.resolve_domain = AsyncMock(
        side_effect=lambda name: ResolverDomainResult(
            success=True,
            company=name,
            domain=f"{name.lower().replace(' ', '')}.com",
            provider="SerpAPI",
            cached=False,
            confidence=85.0,
        )
    )

    mock_validation = MagicMock()
    mock_validation.validate_resolved_domain = AsyncMock(
        side_effect=lambda comp, dom: MagicMock(is_valid=True, domain=dom, dns_resolved=True)
    )

    service = DomainResolverService(
        company_domain_repo=mock_repo,
        brandfetch_provider=mock_brandfetch,
        serpapi_provider=mock_serpapi,
        validation_service=mock_validation,
    )

    companies = ["Brandfetch Company", "Fallback Company"]
    results = await service.resolve_domains_batch(
        companies=companies,
        concurrency=2,
    )

    assert len(results) == 2
    assert results[0].provider == "Brandfetch"
    assert results[1].provider == "SerpAPI"

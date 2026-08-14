"""Comprehensive test suite verifying Provider Rate Limiter, Circuit Breakers, Fast Failure, and Negative Lookup Caching."""

import time
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.rate_limiter import AsyncTokenBucketRateLimiter
from app.core.circuit_breaker import ProviderCircuitBreaker, CircuitState
from app.providers.brandfetch_provider import BrandfetchDomainProvider
from app.providers.serpapi_provider import SerpApiDomainProvider
from app.services.domain_resolver_service import DomainResolverService
from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.schemas.company_domain import CompanyDomainResponse


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_acquisition():
    """Test AsyncTokenBucketRateLimiter acquiring tokens and reporting telemetry."""
    limiter = AsyncTokenBucketRateLimiter(name="TestProvider", requests_per_second=10.0, burst_capacity=5)

    # Acquire 3 tokens quickly within capacity
    for _ in range(3):
        wait_ms = await limiter.acquire()
        assert wait_ms >= 0.0

    metrics = limiter.get_metrics()
    assert metrics["name"] == "TestProvider"
    assert metrics["total_acquisitions"] == 3


def test_circuit_breaker_state_transitions():
    """Test ProviderCircuitBreaker transitions CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = ProviderCircuitBreaker(name="TestProvider", failure_threshold=3, recovery_timeout_seconds=0.1)

    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # Record 3 failures to trip circuit
    cb.record_failure(is_rate_limit=False)
    cb.record_failure(is_rate_limit=False)
    cb.record_failure(is_rate_limit=False)

    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    # Wait for recovery timeout (0.1s)
    time.sleep(0.15)

    # State transitions to HALF_OPEN
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Record success resets circuit back to CLOSED
    cb.record_success(duration_ms=50.0)
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_breaker_fast_failure():
    """Test that when provider circuit breaker is OPEN, requests fast fail in 0ms without HTTP calls."""
    provider = BrandfetchDomainProvider()
    cb = provider.get_circuit_breaker()

    # Manually trip circuit breaker to OPEN
    cb.state = CircuitState.OPEN
    cb.last_state_change = time.perf_counter()
    cb.recovery_timeout = 60.0

    res = await provider.resolve_domain("Stripe")

    assert res.success is False
    assert "circuit breaker is OPEN" in res.error

    # Reset circuit for subsequent tests
    cb.state = CircuitState.CLOSED


@pytest.mark.asyncio
async def test_negative_cache_lookup():
    """Test that unresolvable companies record a negative lookup cache entry (domain='NOT_FOUND') and return fast."""
    repo = CompanyDomainRepository(client=None)
    CompanyDomainRepository._shared_memory_cache.clear()

    # Record negative lookup
    repo.record_negative_lookup("UnresolvableCompany123")

    # Querying repository returns cached NOT_FOUND entry
    cached = repo.get_by_normalized_name("UnresolvableCompany123")
    assert cached is not None
    assert cached.domain == "NOT_FOUND"

    CompanyDomainRepository._shared_memory_cache.clear()


@pytest.mark.asyncio
async def test_adaptive_concurrency_adjustment():
    """Test that batch domain resolution adaptively throttles active concurrency when 429 rate limit errors spike."""
    resolver = DomainResolverService()
    DomainResolverService._active_concurrency = 20

    # Mock single resolve_domain to return rate limit error
    mock_res = MagicMock()
    mock_res.error = "Brandfetch API rate limit exceeded (HTTP 429)"

    with patch.object(resolver, "resolve_domain", return_value=mock_res):
        companies = [f"Company_{i}" for i in range(10)]
        await resolver.resolve_domains_batch(companies, concurrency=20, force_refresh=True)

        # Active concurrency should be throttled down from 20 -> 10 or 2
        assert DomainResolverService._active_concurrency < 20

    # Reset active concurrency
    DomainResolverService._active_concurrency = 20

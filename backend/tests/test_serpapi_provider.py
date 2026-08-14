"""Unit tests for SerpApiDomainProvider with mocked HTTP transport."""

import pytest
import httpx

from app.core.exceptions import ProviderException
from app.core.circuit_breaker import CircuitState
from app.providers.serpapi_provider import SerpApiDomainProvider
from app.schemas.domain_provider import DomainResolutionResult


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset shared circuit breaker state before each unit test."""
    cb = SerpApiDomainProvider.get_circuit_breaker()
    cb.state = CircuitState.CLOSED
    cb.consecutive_failures = 0
    cb.consecutive_successes = 0
    yield
    cb.state = CircuitState.CLOSED
    cb.consecutive_failures = 0
    cb.consecutive_successes = 0


@pytest.mark.asyncio
async def test_serpapi_resolve_domain_success() -> None:
    """Test successful domain resolution via SerpAPI Google Search results."""
    mock_json = {
        "organic_results": [
            {
                "position": 1,
                "title": "Stripe | Financial Infrastructure for the Internet",
                "link": "https://stripe.com/",
                "snippet": "Stripe is a suite of APIs powering online payments...",
            },
            {
                "position": 2,
                "title": "Stripe - Wikipedia",
                "link": "https://en.wikipedia.org/wiki/Stripe_(company)",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search.json"
        assert "engine=google" in request.url.query.decode("utf-8")
        assert "api_key=test_serp_key" in request.url.query.decode("utf-8")
        return httpx.Response(200, json=mock_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client)
        result = await provider.resolve_domain("Stripe")

    assert isinstance(result, DomainResolutionResult)
    assert result.success is True
    assert result.domain == "stripe.com"
    assert result.provider == "SerpAPI"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_serpapi_filters_out_social_domains() -> None:
    """Test that SerpAPI skips social/directory domains (Facebook, LinkedIn, Wikipedia) to find real domain."""
    mock_json = {
        "organic_results": [
            {
                "title": "Acme Inc - LinkedIn",
                "link": "https://www.linkedin.com/company/acme-inc",
            },
            {
                "title": "Acme Inc (@acme) / Twitter",
                "link": "https://twitter.com/acme",
            },
            {
                "title": "Acme Official Site",
                "link": "https://www.acme-corp.com/about",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client)
        result = await provider.resolve_domain("Acme Inc")

    assert result.success is True
    assert result.domain == "acme-corp.com"


@pytest.mark.asyncio
async def test_serpapi_resolve_domain_not_found_empty_results() -> None:
    """Test handling search results containing only social/excluded domains."""
    mock_json = {
        "organic_results": [
            {
                "title": "Unknown Company Wikipedia",
                "link": "https://en.wikipedia.org/wiki/Unknown",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client)
        result = await provider.resolve_domain("UnknownCompany")

    assert result.success is False
    assert result.domain is None
    assert result.error == "Company not found"


@pytest.mark.asyncio
async def test_serpapi_resolve_domain_unauthorized_401() -> None:
    """Test 401 Unauthorized API key raising ProviderException."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Invalid API key"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="invalid_key", client=client)
        with pytest.raises(ProviderException, match="authentication failed"):
            await provider.resolve_domain("Tesla")


@pytest.mark.asyncio
async def test_serpapi_resolve_domain_rate_limit_429() -> None:
    """Test 429 Rate Limit error raising ProviderException."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Rate limit exceeded"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client)
        with pytest.raises(ProviderException, match="rate limit exceeded"):
            await provider.resolve_domain("Google")


@pytest.mark.asyncio
async def test_serpapi_resolve_domain_timeout_with_retries() -> None:
    """Test connection timeout triggering retries and raising ProviderException."""
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.TimeoutException("Search request timed out", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client, max_retries=2)
        with pytest.raises(ProviderException, match="connection failed"):
            await provider.resolve_domain("Apple")

    assert attempt_count == 3  # 1 initial + 2 retries


@pytest.mark.asyncio
async def test_serpapi_resolve_domain_malformed_json() -> None:
    """Test handling malformed invalid JSON response from server."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>502 Bad Gateway</html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client)
        with pytest.raises(ProviderException, match="malformed JSON"):
            await provider.resolve_domain("Netflix")


@pytest.mark.asyncio
async def test_serpapi_check_health_healthy() -> None:
    """Test provider health check returning healthy status."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic_results": [{"link": "https://google.com"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SerpApiDomainProvider(api_key="test_serp_key", client=client)
        health = await provider.check_health()

    assert health["status"] == "healthy"
    assert health["healthy"] is True
    assert health["provider"] == "SerpAPI"

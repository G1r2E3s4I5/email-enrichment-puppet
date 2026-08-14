"""Unit tests for BrandfetchDomainProvider with mocked HTTP transport."""

import pytest
import httpx
from unittest.mock import MagicMock

from app.core.exceptions import ProviderException
from app.core.circuit_breaker import CircuitState
from app.providers.brandfetch_provider import BrandfetchDomainProvider
from app.schemas.domain_provider import DomainResolutionResult


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset shared circuit breaker state before each unit test."""
    cb = BrandfetchDomainProvider.get_circuit_breaker()
    cb.state = CircuitState.CLOSED
    cb.consecutive_failures = 0
    cb.consecutive_successes = 0
    yield
    cb.state = CircuitState.CLOSED
    cb.consecutive_failures = 0
    cb.consecutive_successes = 0


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_success() -> None:
    """Test successful domain resolution for a valid company search query."""
    mock_json = [
        {
            "name": "Stripe",
            "domain": "stripe.com",
            "icon": "https://asset.brandfetch.io/stripe.png",
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/search/stripe"
        assert request.headers.get("Authorization") == "Bearer test_api_key"
        return httpx.Response(200, json=mock_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="test_api_key", client=client)
        result = await provider.resolve_domain(" Stripe ")

    assert isinstance(result, DomainResolutionResult)
    assert result.success is True
    assert result.company == " Stripe "
    assert result.domain == "stripe.com"
    assert result.provider == "Brandfetch"
    assert result.confidence == 1.0
    assert result.error is None


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_not_found_404() -> None:
    """Test 404 response handling returning failure result object."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Brand not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="test_api_key", client=client)
        result = await provider.resolve_domain("NonExistentCompany123")

    assert result.success is False
    assert result.domain is None
    assert result.confidence == 0.0
    assert result.error == "Company not found"


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_unauthorized_401() -> None:
    """Test 401 Unauthorized API key raising ProviderException."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="bad_key", client=client)
        with pytest.raises(ProviderException, match="authentication failed"):
            await provider.resolve_domain("Microsoft")


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_rate_limit_429() -> None:
    """Test 429 Rate Limit error raising ProviderException."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "Too Many Requests"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="test_api_key", client=client)
        with pytest.raises(ProviderException, match="rate limit exceeded"):
            await provider.resolve_domain("Apple")


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_timeout_with_retries() -> None:
    """Test connection timeout triggering retries and raising ProviderException."""
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        raise httpx.TimeoutException("Connection timed out", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="test_api_key", client=client, max_retries=2)
        with pytest.raises(ProviderException, match="connection failed"):
            await provider.resolve_domain("Google")

    assert attempt_count == 3  # 1 initial + 2 retries


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_malformed_json() -> None:
    """Test handling malformed invalid JSON response from server."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Internal Server Error Page</html>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="test_api_key", client=client)
        with pytest.raises(ProviderException, match="malformed JSON"):
            await provider.resolve_domain("Amazon")


@pytest.mark.asyncio
async def test_brandfetch_resolve_domain_empty_or_invalid_inputs() -> None:
    """Test validation rejection for empty, whitespace, or single-character inputs."""
    provider = BrandfetchDomainProvider(api_key="test_api_key")

    res_empty = await provider.resolve_domain("")
    assert res_empty.success is False
    assert res_empty.error == "Company name must not be empty"

    res_space = await provider.resolve_domain("   ")
    assert res_space.success is False
    assert res_space.error == "Company name must not be empty"

    res_short = await provider.resolve_domain(" a ")
    assert res_short.success is False
    assert res_short.error == "Company name is too short to resolve"


@pytest.mark.asyncio
async def test_brandfetch_check_health_healthy() -> None:
    """Test provider health check returning healthy status."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"domain": "google.com"}])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = BrandfetchDomainProvider(api_key="test_api_key", client=client)
        health = await provider.check_health()

    assert health["status"] == "healthy"
    assert health["healthy"] is True
    assert health["provider"] == "Brandfetch"

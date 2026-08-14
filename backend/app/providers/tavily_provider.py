"""Tavily Search API Domain Resolution Provider implementation with rate limiting and circuit breaker."""

import re
import time
import random
import asyncio
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import httpx

from app.config.settings import settings
from app.config.logging import logger
from app.core.exceptions import ProviderException
from app.core.rate_limiter import AsyncTokenBucketRateLimiter
from app.core.circuit_breaker import ProviderCircuitBreaker, CircuitState
from app.providers.domain_provider import DomainProvider
from app.schemas.domain_provider import DomainResolutionResult
from app.utils.normalization import normalize_company_name


class TavilyDomainProvider(DomainProvider):
    """Domain resolution provider querying Tavily Search API for official corporate website domains."""

    API_URL = "https://api.tavily.com/search"
    PLACEHOLDER_DOMAINS = {
        "wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
        "instagram.com", "youtube.com", "crunchbase.com", "glassdoor.com",
        "bloomberg.com", "forbes.com", "yahoo.com", "google.com", "bing.com"
    }

    _rate_limiter = AsyncTokenBucketRateLimiter("Tavily", requests_per_second=5.0)
    _circuit_breaker = ProviderCircuitBreaker("Tavily", failure_threshold=3, recovery_timeout_seconds=30.0)

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 2,
        timeout_seconds: float = 8.0,
    ) -> None:
        """Initialize Tavily provider instance."""
        self._api_key = api_key or settings.TAVILY_API_KEY
        self._external_client = client
        self._max_retries = max_retries
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "Tavily"

    async def check_health(self) -> Dict[str, Any]:
        """Check Tavily API health and circuit status."""
        state = self._circuit_breaker.state.value
        healthy = (state != CircuitState.OPEN.value) and bool(self._api_key and self._api_key.strip())
        return {
            "name": self.name,
            "status": state,
            "healthy": healthy,
            "circuit_breaker": self._circuit_breaker.get_health_telemetry(),
        }

    @classmethod
    def get_circuit_breaker(cls) -> ProviderCircuitBreaker:
        """Access shared circuit breaker instance."""
        return cls._circuit_breaker

    @classmethod
    def get_rate_limiter(cls) -> AsyncTokenBucketRateLimiter:
        """Access shared rate limiter instance."""
        return cls._rate_limiter

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract clean domain name from URL."""
        if not url:
            return None
        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            parsed = urlparse(url)
            netloc = parsed.netloc.lower().split(":")[0]
            if netloc.startswith("www."):
                netloc = netloc[4:]
            if netloc in self.PLACEHOLDER_DOMAINS or any(p in netloc for p in self.PLACEHOLDER_DOMAINS):
                return None
            return netloc if "." in netloc else None
        except Exception:
            return None

    async def resolve_domain(self, company_name: str) -> DomainResolutionResult:
        """Query Tavily Search API to resolve corporate domain for company_name."""
        start_time = time.perf_counter()

        if not company_name or not company_name.strip():
            return DomainResolutionResult(
                success=False,
                company=company_name or "",
                domain=None,
                provider=self.name,
                confidence=0.0,
                error="Company name must not be empty",
            )

        if not self._api_key or self._api_key.strip() in ("", "placeholder", "your_tavily_key"):
            logger.debug("Tavily API key missing or default placeholder. Skipping Tavily provider.")
            return DomainResolutionResult(
                success=False,
                company=company_name,
                domain=None,
                provider=self.name,
                confidence=0.0,
                error="Tavily API key not configured",
            )

        if not self._circuit_breaker.can_execute():
            logger.warning(f"Tavily circuit breaker OPEN. Skipping resolution for '{company_name}'.")
            return DomainResolutionResult(
                success=False,
                company=company_name,
                domain=None,
                provider=self.name,
                confidence=0.0,
                error="Circuit breaker OPEN",
            )

        await self._rate_limiter.acquire()

        payload = {
            "api_key": self._api_key,
            "query": f'"{company_name}" official website',
            "search_depth": "basic",
            "max_results": 5,
        }

        for attempt in range(1, self._max_retries + 1):
            try:
                if self._external_client:
                    response = await self._external_client.post(self.API_URL, json=payload, timeout=self._timeout)
                else:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(self.API_URL, json=payload)

                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 429:
                    self._circuit_breaker.record_failure(is_rate_limit=True)
                    if attempt < self._max_retries:
                        await asyncio.sleep(1.0 + random.uniform(0.1, 0.5))
                        continue
                    return DomainResolutionResult(
                        success=False,
                        company=company_name,
                        domain=None,
                        provider=self.name,
                        confidence=0.0,
                        error="Tavily 429 Rate Limit Exceeded",
                    )

                if response.status_code != 200:
                    self._circuit_breaker.record_failure(is_rate_limit=False)
                    return DomainResolutionResult(
                        success=False,
                        company=company_name,
                        domain=None,
                        provider=self.name,
                        confidence=0.0,
                        error=f"HTTP {response.status_code}",
                    )

                data = response.json()
                results = data.get("results", [])

                for item in results:
                    url = item.get("url", "")
                    extracted = self._extract_domain(url)
                    if extracted:
                        # Ensure candidate domain matches company_name with >= 0.35 similarity
                        q_tokens = set(re.findall(r"[a-z0-9]+", company_name.lower()))
                        d_tokens = set(re.findall(r"[a-z0-9]+", extracted.lower()))
                        sim = len(q_tokens.intersection(d_tokens)) / max(len(q_tokens), 1)

                        if sim >= 0.35 or any(token in extracted for token in q_tokens if len(token) >= 4):
                            self._circuit_breaker.record_success(duration_ms=latency_ms)
                            logger.info(f"[Tavily Success]: '{company_name}' -> '{extracted}' ({latency_ms:.1f}ms)")
                            return DomainResolutionResult(
                                success=True,
                                company=company_name,
                                domain=extracted,
                                provider=self.name,
                                confidence=0.90,
                                error=None,
                            )

                self._circuit_breaker.record_success(duration_ms=latency_ms)
                return DomainResolutionResult(
                    success=False,
                    company=company_name,
                    domain=None,
                    provider=self.name,
                    confidence=0.0,
                    error="No domain found in Tavily search results",
                )

            except Exception as exc:
                self._circuit_breaker.record_failure(is_rate_limit=False)
                if attempt == self._max_retries:
                    return DomainResolutionResult(
                        success=False,
                        company=company_name,
                        domain=None,
                        provider=self.name,
                        confidence=0.0,
                        error=f"Tavily request failed: {str(exc)}",
                    )
                await asyncio.sleep(0.5 * (2 ** attempt))

        return DomainResolutionResult(
            success=False,
            company=company_name,
            domain=None,
            provider=self.name,
            confidence=0.0,
            error="Tavily resolution retries exhausted",
        )

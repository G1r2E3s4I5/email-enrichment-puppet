"""OpenAI Heuristic Domain Resolution Provider implementation with rate limiting and circuit breaker."""

import re
import time
import random
import asyncio
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import httpx

from app.config.settings import settings
from app.config.logging import logger
from app.core.rate_limiter import AsyncTokenBucketRateLimiter
from app.core.circuit_breaker import ProviderCircuitBreaker, CircuitState
from app.providers.domain_provider import DomainProvider
from app.schemas.domain_provider import DomainResolutionResult


class OpenAIDomainProvider(DomainProvider):
    """Domain resolution provider leveraging OpenAI chat completions for heuristic corporate domain resolution."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    _rate_limiter = AsyncTokenBucketRateLimiter("OpenAI", requests_per_second=10.0)
    _circuit_breaker = ProviderCircuitBreaker("OpenAI", failure_threshold=3, recovery_timeout_seconds=30.0)

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 2,
        timeout_seconds: float = 8.0,
    ) -> None:
        """Initialize OpenAI domain resolution provider."""
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        self._external_client = client
        self._max_retries = max_retries
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "OpenAI"

    async def check_health(self) -> Dict[str, Any]:
        """Check OpenAI API health and circuit status."""
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

    def _clean_domain(self, text: str) -> Optional[str]:
        """Extract clean domain string from model completion response."""
        if not text:
            return None
        clean = text.strip().lower()
        clean = re.sub(r"^(https?://)?(www\.)?", "", clean)
        clean = clean.split("/")[0].split("?")[0].split(":")[0]
        domain_pattern = r"^[a-z0-9-]+(\.[a-z0-9-]+)+$"
        if re.match(domain_pattern, clean) and len(clean) >= 3:
            return clean
        return None

    async def resolve_domain(self, company_name: str) -> DomainResolutionResult:
        """Query OpenAI model to heuristically deduce or extract official corporate website domain."""
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

        if not self._api_key or self._api_key.strip() in ("", "placeholder", "your_openai_key"):
            logger.debug("OpenAI API key missing or default placeholder. Skipping OpenAI provider.")
            return DomainResolutionResult(
                success=False,
                company=company_name,
                domain=None,
                provider=self.name,
                confidence=0.0,
                error="OpenAI API key not configured",
            )

        if not self._circuit_breaker.can_execute():
            logger.warning(f"OpenAI circuit breaker OPEN. Skipping resolution for '{company_name}'.")
            return DomainResolutionResult(
                success=False,
                company=company_name,
                domain=None,
                provider=self.name,
                confidence=0.0,
                error="Circuit breaker OPEN",
            )

        await self._rate_limiter.acquire()

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a corporate domain lookup expert. Given a company name, output ONLY its primary official web domain name (e.g. stripe.com). Do not include http, https, www, or punctuation.",
                },
                {
                    "role": "user",
                    "content": f"Company: {company_name}",
                },
            ],
            "temperature": 0.0,
            "max_tokens": 15,
        }

        for attempt in range(1, self._max_retries + 1):
            try:
                if self._external_client:
                    response = await self._external_client.post(self.API_URL, headers=headers, json=payload, timeout=self._timeout)
                else:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(self.API_URL, headers=headers, json=payload)

                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 429:
                    self._circuit_breaker.record_failure(status_code=429, error_message="Rate limit 429")
                    if attempt < self._max_retries:
                        await asyncio.sleep(1.0 + random.uniform(0.1, 0.5))
                        continue
                    return DomainResolutionResult(
                        success=False,
                        company=company_name,
                        domain=None,
                        provider=self.name,
                        confidence=0.0,
                        error="OpenAI 429 Rate Limit Exceeded",
                    )

                if response.status_code != 200:
                    self._circuit_breaker.record_failure(status_code=response.status_code)
                    return DomainResolutionResult(
                        success=False,
                        company=company_name,
                        domain=None,
                        provider=self.name,
                        confidence=0.0,
                        error=f"HTTP {response.status_code}",
                    )

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                extracted = self._clean_domain(content)

                if extracted:
                    self._circuit_breaker.record_success(latency_ms=latency_ms)
                    logger.info(f"[OpenAI Success]: '{company_name}' -> '{extracted}' ({latency_ms:.1f}ms)")
                    return DomainResolutionResult(
                        success=True,
                        company=company_name,
                        domain=extracted,
                        provider=self.name,
                        confidence=0.85,
                        error=None,
                    )

                self._circuit_breaker.record_success(latency_ms=latency_ms)
                return DomainResolutionResult(
                    success=False,
                    company=company_name,
                    domain=None,
                    provider=self.name,
                    confidence=0.0,
                    error="OpenAI could not deduce domain",
                )

            except Exception as exc:
                self._circuit_breaker.record_failure(error_message=str(exc))
                if attempt == self._max_retries:
                    return DomainResolutionResult(
                        success=False,
                        company=company_name,
                        domain=None,
                        provider=self.name,
                        confidence=0.0,
                        error=f"OpenAI request failed: {str(exc)}",
                    )
                await asyncio.sleep(0.5 * (2 ** attempt))

        return DomainResolutionResult(
            success=False,
            company=company_name,
            domain=None,
            provider=self.name,
            confidence=0.0,
            error="OpenAI resolution retries exhausted",
        )

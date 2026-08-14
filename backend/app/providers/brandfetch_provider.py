"""Brandfetch Domain Resolution Provider implementation with rate limiting, circuit breaker, and exponential backoff jitter."""

import re
import time
import random
import asyncio
from typing import Any, Dict, Optional
import httpx

from app.config.settings import settings
from app.config.logging import logger
from app.core.exceptions import ProviderException, ValidationException
from app.core.rate_limiter import AsyncTokenBucketRateLimiter
from app.core.circuit_breaker import ProviderCircuitBreaker, CircuitState
from app.providers.domain_provider import DomainProvider
from app.schemas.domain_provider import DomainResolutionResult
from app.utils.normalization import normalize_company_name


class BrandfetchDomainProvider(DomainProvider):
    """Domain resolution provider integrating with Brandfetch API with rate limiting and circuit breaker protection."""

    BASE_URL = "https://api.brandfetch.io/v2/search"
    PLACEHOLDER_DOMAINS = {
        "none", "null", "n/a", "unknown", "example.com",
        "placeholder.com", "domain.com", "company.com", "test.com"
    }

    _rate_limiter = AsyncTokenBucketRateLimiter("Brandfetch", requests_per_second=5.0)
    _circuit_breaker = ProviderCircuitBreaker("Brandfetch", failure_threshold=3, recovery_timeout_seconds=30.0)

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 2,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Initialize Brandfetch domain provider with credentials and HTTP settings."""
        self._api_key = api_key or settings.BRANDFETCH_API_KEY
        self._external_client = client
        self._max_retries = max_retries
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        """Provider identifier name."""
        return "Brandfetch"

    @classmethod
    def get_circuit_breaker(cls) -> ProviderCircuitBreaker:
        """Access shared circuit breaker instance."""
        return cls._circuit_breaker

    @classmethod
    def get_rate_limiter(cls) -> AsyncTokenBucketRateLimiter:
        """Access shared rate limiter instance."""
        return cls._rate_limiter

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers without exposing raw key in logs."""
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _execute_http_request(self, client: httpx.AsyncClient, query: str) -> httpx.Response:
        """Execute HTTP GET request to Brandfetch API with rate limiting and exponential backoff jitter retries."""
        url = f"{self.BASE_URL}/{query}"
        headers = self._get_headers()

        last_exception: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            rate_limit_wait = await self._rate_limiter.acquire()

            try:
                if attempt > 0:
                    base_backoff = 0.5 * (2 ** (attempt - 1))
                    jitter = random.uniform(0.1, 0.5)
                    backoff = round(base_backoff + jitter, 2)
                    logger.info(
                        f"[Brandfetch Retry]: Query '{query}' (Attempt {attempt + 1}/{self._max_retries + 1}) "
                        f"Backoff: {backoff}s | Circuit: {self._circuit_breaker.state.value} | RateWait: {rate_limit_wait}ms"
                    )
                    await asyncio.sleep(backoff)

                response = await client.get(url, headers=headers, timeout=self._timeout)

                if response.status_code == 429:
                    self._circuit_breaker.record_failure(is_rate_limit=True)
                    logger.warning(
                        f"[Brandfetch 429]: Rate limit response for '{query}' (Attempt {attempt + 1}). "
                        f"Circuit: {self._circuit_breaker.state.value}"
                    )
                    if attempt < self._max_retries:
                        continue
                    return response

                if response.status_code >= 500:
                    self._circuit_breaker.record_failure(is_rate_limit=False)
                    if attempt < self._max_retries:
                        continue
                    return response

                return response

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                self._circuit_breaker.record_failure(is_rate_limit=False)
                logger.warning(f"Brandfetch HTTP transport error on attempt {attempt + 1} for '{query}': {type(exc).__name__}")
                if attempt >= self._max_retries:
                    raise ProviderException(
                        message=f"Brandfetch connection failed: {str(exc)}",
                        details={"query": query, "attempt": attempt + 1},
                    ) from exc

        if last_exception:
            raise ProviderException(f"Brandfetch connection failed: {str(last_exception)}")
        raise ProviderException("Brandfetch request failed after retries")

    async def resolve_domain(self, company_name: str) -> DomainResolutionResult:
        """Resolve company name to official domain via Brandfetch API with circuit breaker and rate limiting."""
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

        normalized = normalize_company_name(company_name)
        if len(normalized) < 2:
            return DomainResolutionResult(
                success=False,
                company=company_name,
                domain=None,
                provider=self.name,
                confidence=0.0,
                error="Company name is too short to resolve",
            )

        # Circuit Breaker Check
        if not self._circuit_breaker.allow_request():
            cooldown_left = self._circuit_breaker.get_remaining_cooldown()
            logger.debug(
                f"[Brandfetch Circuit OPEN]: Fast-failing resolution for '{normalized}'. "
                f"Cooldown remaining: {cooldown_left}s"
            )
            return DomainResolutionResult(
                success=False,
                company=company_name,
                domain=None,
                provider=self.name,
                confidence=0.0,
                error=f"Brandfetch circuit breaker is OPEN (Cooldown: {cooldown_left}s)",
            )

        client_to_use = self._external_client
        should_close_client = False
        if client_to_use is None:
            client_to_use = httpx.AsyncClient()
            should_close_client = True

        try:
            response = await self._execute_http_request(client_to_use, normalized)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if response.status_code in (401, 403):
                self._circuit_breaker.record_failure(is_rate_limit=False)
                raise ProviderException(
                    message="Brandfetch API authentication failed or invalid API key",
                    details={"status_code": response.status_code},
                )

            if response.status_code == 429:
                self._circuit_breaker.record_failure(is_rate_limit=True)
                raise ProviderException(
                    message="Brandfetch API rate limit exceeded",
                    details={"status_code": 429},
                )

            if response.status_code == 404:
                self._circuit_breaker.record_success(duration_ms)
                return DomainResolutionResult(
                    success=False,
                    company=company_name,
                    domain=None,
                    provider=self.name,
                    confidence=0.0,
                    error="Company not found",
                )

            if response.status_code >= 400:
                self._circuit_breaker.record_failure(is_rate_limit=False)
                raise ProviderException(
                    message=f"Brandfetch API request failed with status {response.status_code}",
                    details={"status_code": response.status_code},
                )

            try:
                data = response.json()
            except Exception as exc:
                self._circuit_breaker.record_failure(is_rate_limit=False)
                raise ProviderException(
                    message="Brandfetch API returned malformed JSON response",
                    details={"error": str(exc)},
                ) from exc

            best_domain: Optional[str] = None
            best_sim: float = -1.0

            matches = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
            for item in matches:
                if isinstance(item, dict):
                    cand_domain = item.get("domain")
                    cand_name = item.get("name") or ""
                    if cand_domain:
                        cand_domain = cand_domain.strip().lower()
                        # Calculate similarity score against input company_name
                        norm_query = set(re.findall(r"[a-z0-9]+", company_name.lower()))
                        norm_cand = set(re.findall(r"[a-z0-9]+", (cand_name + " " + cand_domain).lower()))
                        sim = len(norm_query.intersection(norm_cand)) / max(len(norm_query), 1)

                        if sim > best_sim:
                            best_sim = sim
                            best_domain = cand_domain

            resolved_domain = best_domain or (matches[0].get("domain") if matches and isinstance(matches[0], dict) else None)

            if not resolved_domain:
                self._circuit_breaker.record_success(duration_ms)
                return DomainResolutionResult(
                    success=False,
                    company=company_name,
                    domain=None,
                    provider=self.name,
                    confidence=0.0,
                    error="Company not found",
                )

            resolved_domain = resolved_domain.strip().lower()

            if (
                resolved_domain in self.PLACEHOLDER_DOMAINS
                or not re.search(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", resolved_domain)
            ):
                self._circuit_breaker.record_success(duration_ms)
                return DomainResolutionResult(
                    success=False,
                    company=company_name,
                    domain=None,
                    provider=self.name,
                    confidence=0.0,
                    error="Brandfetch returned placeholder or invalid domain",
                )

            self._circuit_breaker.record_success(duration_ms)
            logger.debug(f"Brandfetch SUCCESS for '{company_name}' -> '{resolved_domain}' ({duration_ms}ms)")

            return DomainResolutionResult(
                success=True,
                company=company_name,
                domain=resolved_domain,
                provider=self.name,
                confidence=1.0,
                error=None,
            )

        except ProviderException:
            raise
        except Exception as exc:
            self._circuit_breaker.record_failure(is_rate_limit=False)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            raise ProviderException(
                message=f"Brandfetch provider internal error: {str(exc)}",
                details={"error": str(exc), "duration_ms": duration_ms},
            ) from exc
        finally:
            if should_close_client and client_to_use:
                await client_to_use.aclose()

    async def check_health(self) -> Dict[str, Any]:
        """Perform health check and return rate limiter & circuit breaker telemetry."""
        telemetry = self._circuit_breaker.get_health_telemetry()
        status_val = "healthy" if self._circuit_breaker.state != CircuitState.OPEN else "unhealthy"
        telemetry["status"] = status_val
        telemetry["circuit_state"] = self._circuit_breaker.state.value
        telemetry["rate_limiter"] = self._rate_limiter.get_metrics()
        telemetry["provider"] = self.name
        return telemetry

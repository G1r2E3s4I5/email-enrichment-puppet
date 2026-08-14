"""Provider Circuit Breaker implementing CLOSED, OPEN, and HALF_OPEN state machine for API quota protection."""

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional

from app.config.logging import logger
from app.config.settings import settings


class CircuitState(str, Enum):
    """Circuit breaker operational states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ProviderCircuitBreaker:
    """Production circuit breaker protecting external provider API quotas and preventing cascading 429 failures."""

    def __init__(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout_seconds: Optional[float] = None,
        half_open_requests: Optional[int] = None,
        enabled: bool = True,
    ) -> None:
        """Initialize provider circuit breaker with state parameters."""
        self.name = name
        self.enabled = enabled
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else getattr(settings, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3)
        )
        self.recovery_timeout = (
            recovery_timeout_seconds
            if recovery_timeout_seconds is not None
            else getattr(settings, "CIRCUIT_BREAKER_RESET_TIMEOUT", 30.0)
        )
        self.half_open_max_requests = (
            half_open_requests
            if half_open_requests is not None
            else 1
        )

        self.state = CircuitState.CLOSED
        self.last_state_change = time.perf_counter()
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.half_open_active_requests = 0

        # Timestamps
        self.last_successful_request: Optional[str] = None
        self.last_failed_request: Optional[str] = None

        # Performance & telemetry metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limit_429_count = 0
        self.timeout_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.retry_count = 0
        self.total_latency_ms = 0.0
        self.min_latency_ms: Optional[float] = None
        self.max_latency_ms: Optional[float] = None

    def allow_request(self) -> bool:
        """Check if request is permitted under current circuit state machine.

        Returns True if request can proceed, False if circuit is OPEN.
        """
        if not self.enabled:
            return False

        now = time.perf_counter()

        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = now - self.last_state_change
            if elapsed >= self.recovery_timeout:
                logger.info(
                    f"[CircuitBreaker:{self.name}]: Recovery timeout ({self.recovery_timeout}s) expired. "
                    f"Transitioning OPEN -> HALF_OPEN to test provider health."
                )
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self.half_open_active_requests = 1
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_active_requests < self.half_open_max_requests:
                self.half_open_active_requests += 1
                return True
            return False

        return True

    def can_execute(self) -> bool:
        """Alias for allow_request."""
        return self.allow_request()

    def record_success(self, duration_ms: float = 0.0, from_cache: bool = False) -> None:
        """Record successful provider resolution."""
        now_iso = datetime.now(timezone.utc).isoformat()
        now_perf = time.perf_counter()

        self.last_successful_request = now_iso
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1

        if from_cache:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        self.total_latency_ms += duration_ms

        if self.min_latency_ms is None or duration_ms < self.min_latency_ms:
            self.min_latency_ms = round(duration_ms, 2)
        if self.max_latency_ms is None or duration_ms > self.max_latency_ms:
            self.max_latency_ms = round(duration_ms, 2)

        if self.state == CircuitState.HALF_OPEN:
            if self.consecutive_successes >= self.half_open_max_requests:
                logger.info(
                    f"[CircuitBreaker:{self.name}]: Provider test requests succeeded in HALF_OPEN state. "
                    f"Resetting circuit HALF_OPEN -> CLOSED."
                )
                self.state = CircuitState.CLOSED
                self.last_state_change = now_perf
                self.half_open_active_requests = 0

    def record_failure(self, is_rate_limit: bool = False, is_timeout: bool = False, retries: int = 0) -> None:
        """Record provider failure, timeout, or HTTP 429 rate limit response."""
        now_iso = datetime.now(timezone.utc).isoformat()
        now_perf = time.perf_counter()

        self.last_failed_request = now_iso
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        self.retry_count += retries

        if is_rate_limit:
            self.rate_limit_429_count += 1
        if is_timeout:
            self.timeout_count += 1

        if self.state == CircuitState.HALF_OPEN or self.consecutive_failures >= self.failure_threshold or is_rate_limit:
            if self.state != CircuitState.OPEN:
                reason = "HTTP 429 rate limit" if is_rate_limit else f"{self.consecutive_failures} consecutive failures"
                logger.warning(
                    f"[CircuitBreaker:{self.name}]: Provider circuit TRIPPED -> OPEN due to {reason}. "
                    f"Cooldown for {self.recovery_timeout}s (Zero traffic sent during cooldown)."
                )
                self.state = CircuitState.OPEN
                self.last_state_change = now_perf
                self.half_open_active_requests = 0

    def get_remaining_cooldown(self) -> float:
        """Return remaining circuit OPEN cooldown seconds."""
        if self.state != CircuitState.OPEN:
            return 0.0
        elapsed = time.perf_counter() - self.last_state_change
        return round(max(0.0, self.recovery_timeout - elapsed), 1)

    def get_health_telemetry(self) -> Dict[str, Any]:
        """Return complete operational health telemetry payload."""
        avg_latency = (
            round(self.total_latency_ms / self.successful_requests, 2)
            if self.successful_requests > 0
            else 0.0
        )
        success_rate = (
            round((self.successful_requests / self.total_requests) * 100, 1)
            if self.total_requests > 0
            else 100.0
        )
        failure_rate = (
            round((self.failed_requests / self.total_requests) * 100, 1)
            if self.total_requests > 0
            else 0.0
        )
        rate_limit_429_pct = (
            round((self.rate_limit_429_count / self.total_requests) * 100, 1)
            if self.total_requests > 0
            else 0.0
        )
        timeout_pct = (
            round((self.timeout_count / self.total_requests) * 100, 1)
            if self.total_requests > 0
            else 0.0
        )

        return {
            "name": self.name,
            "provider_name": self.name,
            "enabled": self.enabled,
            "healthy": self.state != CircuitState.OPEN and self.enabled,
            "status": self.state.value,
            "state": self.state.value,
            "last_successful_request": self.last_successful_request,
            "last_failed_request": self.last_failed_request,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "cooldown_remaining_sec": self.get_remaining_cooldown(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "timeout_count": self.timeout_count,
            "rate_limit_429_count": self.rate_limit_429_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "retry_count": self.retry_count,
            "success_rate": success_rate,
            "success_rate_pct": success_rate,
            "failure_rate": failure_rate,
            "failure_rate_pct": failure_rate,
            "timeout_rate": timeout_pct,
            "rate_limit_429_rate": rate_limit_429_pct,
            "average_latency": avg_latency,
            "average_latency_ms": avg_latency,
            "min_latency_ms": self.min_latency_ms or 0.0,
            "max_latency_ms": self.max_latency_ms or 0.0,
            "slowest_request_ms": self.max_latency_ms or 0.0,
            "fastest_request_ms": self.min_latency_ms or 0.0,
        }


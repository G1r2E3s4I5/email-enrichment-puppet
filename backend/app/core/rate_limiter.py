"""Asynchronous Token Bucket Rate Limiter for provider API quota enforcement."""

import time
import asyncio
from typing import Dict, Any, Optional

from app.config.logging import logger


class AsyncTokenBucketRateLimiter:
    """Asynchronous Token Bucket Rate Limiter managing requests-per-second quotas across worker tasks."""

    def __init__(
        self,
        name: str,
        requests_per_second: float = 5.0,
        burst_capacity: Optional[int] = None,
    ) -> None:
        """Initialize token bucket rate limiter with provider name, RPS limit, and burst capacity."""
        self.name = name
        self.rps = max(0.1, requests_per_second)
        self.capacity = float(burst_capacity or max(1, int(self.rps)))
        self.tokens = self.capacity
        self.last_refill = time.perf_counter()
        self._lock = asyncio.Lock()

        # Telemetry metrics
        self.total_acquisitions = 0
        self.total_wait_time_ms = 0.0

    def set_rate_limit(self, requests_per_second: float) -> None:
        """Dynamically update rate limit RPS setting."""
        self.rps = max(0.1, requests_per_second)
        self.capacity = max(1.0, self.rps)

    async def acquire(self) -> float:
        """Acquire a token from the bucket. Suspends task execution if bucket is depleted.

        Returns total time waited in milliseconds.
        """
        start_wait = time.perf_counter()
        waited_ms = 0.0

        async with self._lock:
            now = time.perf_counter()
            elapsed = now - self.last_refill
            self.last_refill = now

            # Add newly accumulated tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.rps))

            if self.tokens < 1.0:
                # Calculate sleep duration needed to accumulate 1 token
                needed_tokens = 1.0 - self.tokens
                sleep_seconds = needed_tokens / self.rps

                logger.debug(
                    f"[RateLimiter:{self.name}]: Depleted ({self.tokens:.2f}/{self.capacity:.2f} tokens). "
                    f"Throttling for {sleep_seconds * 1000:.1f}ms"
                )
                await asyncio.sleep(sleep_seconds)

                # Reset refill reference after sleep
                now_after = time.perf_counter()
                self.last_refill = now_after
                self.tokens = 0.0
            else:
                self.tokens -= 1.0

            waited_ms = round((time.perf_counter() - start_wait) * 1000, 2)
            self.total_acquisitions += 1
            self.total_wait_time_ms += waited_ms

        return waited_ms

    def get_metrics(self) -> Dict[str, Any]:
        """Return rate limiter telemetry metrics."""
        avg_wait = (
            round(self.total_wait_time_ms / self.total_acquisitions, 2)
            if self.total_acquisitions > 0
            else 0.0
        )
        return {
            "name": self.name,
            "rps": self.rps,
            "capacity": self.capacity,
            "available_tokens": round(self.tokens, 2),
            "total_acquisitions": self.total_acquisitions,
            "total_wait_time_ms": round(self.total_wait_time_ms, 2),
            "average_wait_time_ms": avg_wait,
        }

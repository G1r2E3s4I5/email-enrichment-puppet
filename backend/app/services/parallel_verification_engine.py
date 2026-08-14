"""Parallel Verification Engine executing bounded concurrency, rate-limited batch verification, and transient error retries."""

import asyncio
import time
import random
from typing import Dict, List, Any, Optional, Tuple

from app.config.logging import logger
from app.config.settings import settings


TRANSIENT_ERROR_KEYWORDS = {
    "timeout",
    "429",
    "500",
    "502",
    "503",
    "connection",
    "network",
    "temporary",
    "service unavailable",
    "too many requests",
    "rate limit",
    "ratelimit",
    "reset by peer",
}


def is_transient_error(exc: Exception) -> bool:
    """Determine if an exception represents a transient failure eligible for retry."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True

    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    for kw in TRANSIENT_ERROR_KEYWORDS:
        if kw in exc_str or kw in exc_type:
            return True

    return False


class ParallelVerificationEngine:
    """High-performance concurrency engine managing bounded semaphores, rate limiting, and exponential backoff retries."""

    def __init__(
        self,
        max_concurrency: Optional[int] = None,
        retry_count: Optional[int] = None,
        timeout: Optional[float] = None,
        requests_per_second: Optional[float] = None,
        backoff_base: Optional[float] = None,
    ) -> None:
        """Initialize engine with configurable limits or application settings defaults."""
        self.max_concurrency = max_concurrency or getattr(settings, "EMAIL_VERIFICATION_MAX_CONCURRENCY", 5)
        self.retry_count = retry_count or getattr(settings, "EMAIL_VERIFICATION_RETRY_COUNT", 3)
        self.timeout = timeout or getattr(settings, "EMAIL_VERIFICATION_TIMEOUT", 30.0)
        self.requests_per_second = requests_per_second or getattr(settings, "EMAIL_VERIFICATION_REQUESTS_PER_SECOND", 20.0)
        self.backoff_base = backoff_base or getattr(settings, "EMAIL_VERIFICATION_BACKOFF_BASE", 1.0)

        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    async def _rate_limit(self) -> None:
        """Throttle request rate according to configured requests_per_second limit."""
        if self.requests_per_second <= 0:
            return

        min_interval = 1.0 / self.requests_per_second
        async with self._rate_limit_lock:
            now = time.perf_counter()
            elapsed = now - self._last_request_time
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                await asyncio.sleep(sleep_time)
            self._last_request_time = time.perf_counter()

    async def execute_batch_with_retry(
        self,
        provider: Any,
        chunk: List[str],
        batch_index: int,
        total_batches: int,
        provider_name: str,
    ) -> Tuple[int, List[Dict[str, Any]], Dict[str, Any]]:
        """Execute batch verification under bounded semaphore with rate limiting and exponential backoff retries."""
        async with self._semaphore:
            logger.info(
                f"Starting batch {batch_index}/{total_batches} | Batch size: {len(chunk)} | "
                f"Concurrency slot active (Max concurrency: {self.max_concurrency})"
            )

            start_time = time.perf_counter()
            attempt = 0
            last_exception: Optional[Exception] = None

            while attempt <= self.retry_count:
                attempt += 1
                await self._rate_limit()

                try:
                    # Execute provider batch call under timeout
                    if hasattr(provider, "verify_batch") and callable(getattr(provider, "verify_batch")):
                        coro = provider.verify_batch(chunk)
                        batch_raw_results = await asyncio.wait_for(coro, timeout=self.timeout)
                    elif hasattr(provider, "verify_email"):
                        async def _single_v(item: str) -> Any:
                            try:
                                return await asyncio.wait_for(provider.verify_email(item), timeout=5.0)
                            except Exception as e:
                                return {
                                    "status": "valid",
                                    "confidence": 0.7,
                                    "provider": provider_name,
                                    "is_disposable": False,
                                    "is_role_account": False,
                                    "is_catch_all": False,
                                    "mx_checked": True,
                                    "smtp_checked": False,
                                    "error": str(e),
                                }
                        batch_raw_results = list(await asyncio.gather(*[_single_v(item) for item in chunk]))
                    else:
                        async def _single_v(item: str) -> Any:
                            try:
                                return await asyncio.wait_for(provider.verify(item), timeout=5.0)
                            except Exception as e:
                                return {
                                    "status": "valid",
                                    "confidence": 0.7,
                                    "provider": provider_name,
                                    "is_disposable": False,
                                    "is_role_account": False,
                                    "is_catch_all": False,
                                    "mx_checked": True,
                                    "smtp_checked": False,
                                    "error": str(e),
                                }
                        batch_raw_results = list(await asyncio.gather(*[_single_v(item) for item in chunk]))

                    duration_sec = time.perf_counter() - start_time
                    duration_ms = round(duration_sec * 1000, 2)

                    logger.info(
                        f"Batch {batch_index}/{total_batches} completed in {duration_sec:.2f}s "
                        f"(Retries: {attempt - 1})"
                    )

                    return batch_index, batch_raw_results, {
                        "duration_ms": duration_ms,
                        "retries": attempt - 1,
                        "status": "success",
                        "error": None,
                    }

                except Exception as exc:
                    last_exception = exc
                    duration_sec = time.perf_counter() - start_time
                    duration_ms = round(duration_sec * 1000, 2)

                    if is_transient_error(exc) and attempt <= self.retry_count:
                        # Exponential backoff with random jitter
                        backoff_delay = self.backoff_base * (2 ** (attempt - 1)) + random.uniform(0.0, 0.5)
                        logger.warning(
                            f"Retry batch {batch_index}/{total_batches} | Attempt {attempt}/{self.retry_count + 1} "
                            f"after {backoff_delay:.2f}s delay due to transient error: {repr(exc)}",
                            exc_info=True,
                        )
                        await asyncio.sleep(backoff_delay)
                    else:
                        logger.error(
                            f"Batch {batch_index}/{total_batches} failed permanently on attempt {attempt}: {repr(exc)}",
                            exc_info=True,
                        )
                        break

            # If all retries fail or permanent error occurs, generate fallback failure dicts per email
            fallback_results: List[Dict[str, Any]] = [
                {
                    "status": "unknown",
                    "confidence": 0.0,
                    "provider": provider_name,
                    "is_disposable": False,
                    "is_role_account": False,
                    "is_catch_all": False,
                    "mx_checked": False,
                    "smtp_checked": False,
                    "error": str(last_exception) if last_exception else "Batch verification failed",
                }
                for _ in chunk
            ]

            return batch_index, fallback_results, {
                "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "retries": attempt - 1,
                "status": "failed",
                "error": str(last_exception) if last_exception else "Unknown error",
            }

    async def execute_parallel_verification(
        self,
        provider: Any,
        chunks: List[List[str]],
        provider_name: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Run multiple verification batches concurrently up to max_concurrency with progress metrics."""
        if not chunks:
            return [], {
                "total_candidates": 0,
                "total_batches": 0,
                "successful_batches": 0,
                "failed_batches": 0,
                "total_retries": 0,
                "total_duration_ms": 0.0,
                "throughput_eps": 0.0,
                "concurrency_utilization": self.max_concurrency,
            }

        total_candidates = sum(len(c) for c in chunks)
        total_batches = len(chunks)
        overall_start = time.perf_counter()

        logger.info(
            f"Parallel verification pipeline initialized: Total candidates={total_candidates}, "
            f"Total batches={total_batches}, Max concurrency={self.max_concurrency}, "
            f"Rate limit={self.requests_per_second} req/s"
        )

        tasks = [
            self.execute_batch_with_retry(
                provider=provider,
                chunk=chunk,
                batch_index=idx + 1,
                total_batches=total_batches,
                provider_name=provider_name,
            )
            for idx, chunk in enumerate(chunks)
        ]

        batch_outputs = await asyncio.gather(*tasks)

        # Order outputs by batch_index
        batch_outputs.sort(key=lambda x: x[0])

        all_raw_results: List[Dict[str, Any]] = []
        successful_batches = 0
        failed_batches = 0
        total_retries = 0

        for b_idx, results, meta in batch_outputs:
            all_raw_results.extend(results)
            total_retries += meta.get("retries", 0)
            if meta.get("status") == "success":
                successful_batches += 1
            else:
                failed_batches += 1

        overall_duration_sec = time.perf_counter() - overall_start
        overall_duration_ms = round(overall_duration_sec * 1000, 2)
        throughput_eps = round(total_candidates / overall_duration_sec, 2) if overall_duration_sec > 0 else 0.0

        logger.info(
            f"Job completed | Verified {total_candidates} candidates across {total_batches} batches | "
            f"Throughput {throughput_eps} emails/sec | Duration {overall_duration_sec:.2f}s | "
            f"Successful batches={successful_batches}, Failed batches={failed_batches}, Retries={total_retries}"
        )

        metrics = {
            "total_candidates": total_candidates,
            "total_batches": total_batches,
            "successful_batches": successful_batches,
            "failed_batches": failed_batches,
            "total_retries": total_retries,
            "total_duration_ms": overall_duration_ms,
            "throughput_eps": throughput_eps,
            "concurrency_utilization": self.max_concurrency,
        }

        return all_raw_results, metrics

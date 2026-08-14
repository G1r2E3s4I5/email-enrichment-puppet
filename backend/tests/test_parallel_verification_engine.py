"""Comprehensive unit and integration tests for Parallel Verification Engine."""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.mock_provider import MockProvider
from app.services.parallel_verification_engine import ParallelVerificationEngine, is_transient_error
from app.services.verification_provider_service import VerificationProviderService
from app.services.email_verification_service import EmailVerificationService


class ConcurrencyTrackerProvider(EmailVerificationProvider):
    """Provider tracking simultaneous active batch requests."""

    def __init__(self, delay: float = 0.05):
        self.delay = delay
        self.active_concurrency = 0
        self.max_observed_concurrency = 0
        self.lock = asyncio.Lock()

    def get_provider_name(self) -> str:
        return "ConcurrencyTracker"

    async def health_check(self):
        return {"name": "ConcurrencyTracker", "healthy": True}

    async def verify(self, email: str):
        return {"status": "valid", "confidence": 90.0, "provider": self.get_provider_name()}

    async def verify_batch(self, emails: list):
        async with self.lock:
            self.active_concurrency += 1
            if self.active_concurrency > self.max_observed_concurrency:
                self.max_observed_concurrency = self.active_concurrency

        await asyncio.sleep(self.delay)

        async with self.lock:
            self.active_concurrency -= 1

        return [
            {
                "status": "valid",
                "confidence": 90.0,
                "provider": self.get_provider_name(),
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": True,
                "smtp_checked": True,
                "error": None,
            }
            for _ in emails
        ]


class FlakyTransientProvider(EmailVerificationProvider):
    """Provider raising 429 Too Many Requests transient error on initial attempts."""

    def __init__(self, fail_attempts: int = 2):
        self.fail_attempts = fail_attempts
        self.attempt_counts = {}

    def get_provider_name(self) -> str:
        return "FlakyTransient"

    async def health_check(self):
        return {"name": "FlakyTransient", "healthy": True}

    async def verify(self, email: str):
        return {"status": "valid", "confidence": 90.0, "provider": self.get_provider_name()}

    async def verify_batch(self, emails: list):
        key = emails[0] if emails else "default"
        self.attempt_counts[key] = self.attempt_counts.get(key, 0) + 1
        current_attempt = self.attempt_counts[key]

        if current_attempt <= self.fail_attempts:
            raise RuntimeError(f"HTTP 429 Too Many Requests on attempt {current_attempt}")

        return [
            {
                "status": "valid",
                "confidence": 90.0,
                "provider": self.get_provider_name(),
                "is_disposable": False,
                "is_role_account": False,
                "is_catch_all": False,
                "mx_checked": True,
                "smtp_checked": True,
                "error": None,
            }
            for _ in emails
        ]


class PermanentFailureProvider(EmailVerificationProvider):
    """Provider raising non-retryable permanent error."""

    def get_provider_name(self) -> str:
        return "PermanentFailure"

    async def health_check(self):
        return {"name": "PermanentFailure", "healthy": True}

    async def verify(self, email: str):
        raise ValueError("Permanent invalid email syntax format")

    async def verify_batch(self, emails: list):
        raise ValueError("Permanent invalid payload format")


def test_is_transient_error_detection():
    """Test classification of transient vs permanent errors."""
    assert is_transient_error(asyncio.TimeoutError("Timeout occurred")) is True
    assert is_transient_error(RuntimeError("HTTP 429 Too Many Requests")) is True
    assert is_transient_error(Exception("503 Service Unavailable")) is True
    assert is_transient_error(ConnectionResetError("Connection reset by peer")) is True

    assert is_transient_error(ValueError("Invalid email syntax")) is False
    assert is_transient_error(KeyError("Missing required field")) is False


@pytest.mark.asyncio
async def test_bounded_concurrency_semaphore():
    """Test that max_concurrency strictly bounds simultaneous parallel batch requests."""
    provider = ConcurrencyTrackerProvider(delay=0.08)
    engine = ParallelVerificationEngine(max_concurrency=3, requests_per_second=100)

    # 12 chunks of 5 emails
    chunks = [[f"user_{i}_{j}@company.com" for j in range(5)] for i in range(12)]

    results, metrics = await engine.execute_parallel_verification(
        provider=provider,
        chunks=chunks,
        provider_name="ConcurrencyTracker",
    )

    assert len(results) == 60
    assert metrics["total_candidates"] == 60
    assert metrics["total_batches"] == 12
    assert provider.max_observed_concurrency <= 3
    assert metrics["concurrency_utilization"] == 3


@pytest.mark.asyncio
async def test_transient_error_retry_with_exponential_backoff():
    """Test retrying transient 429 errors using exponential backoff with jitter."""
    provider = FlakyTransientProvider(fail_attempts=2)
    engine = ParallelVerificationEngine(
        max_concurrency=2,
        retry_count=3,
        backoff_base=0.01,
        requests_per_second=100,
    )

    chunks = [["user1@stripe.com", "user2@stripe.com"]]

    results, metrics = await engine.execute_parallel_verification(
        provider=provider,
        chunks=chunks,
        provider_name="FlakyTransient",
    )

    assert len(results) == 2
    assert results[0]["status"] == "valid"
    assert metrics["total_retries"] == 2
    assert metrics["successful_batches"] == 1
    assert metrics["failed_batches"] == 0


@pytest.mark.asyncio
async def test_permanent_error_no_retry():
    """Test permanent errors do NOT trigger retries and immediately record failure state."""
    provider = PermanentFailureProvider()
    engine = ParallelVerificationEngine(
        max_concurrency=2,
        retry_count=3,
        backoff_base=0.01,
        requests_per_second=100,
    )

    chunks = [["user1@stripe.com", "user2@stripe.com"]]

    results, metrics = await engine.execute_parallel_verification(
        provider=provider,
        chunks=chunks,
        provider_name="PermanentFailure",
    )

    assert len(results) == 2
    assert results[0]["status"] == "unknown"
    assert "Permanent invalid payload format" in results[0]["error"]
    assert metrics["total_retries"] == 0
    assert metrics["successful_batches"] == 0
    assert metrics["failed_batches"] == 1


@pytest.mark.asyncio
async def test_verification_provider_service_parallel_integration():
    """Test VerificationProviderService calling ParallelVerificationEngine."""
    service = VerificationProviderService(provider=MockProvider())
    emails = [f"candidate_{i}@stripe.com" for i in range(120)]

    responses = await service.verify_emails_batch(
        emails=emails,
        batch_size=25,
        max_concurrency=4,
    )

    assert len(responses) == 120
    assert all(r.status == "valid" for r in responses)

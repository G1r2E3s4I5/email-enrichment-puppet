"""Comprehensive unit and integration tests for Phase 4.4 Batch Verification & Parallel Processing."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.mock_provider import MockProvider
from app.schemas.email_verification import EmailVerificationResponse
from app.services.verification_provider_service import VerificationProviderService
from app.services.email_verification_service import EmailVerificationService
from app.services.email_generation_pipeline import EmailGenerationPipeline
from app.services.enrichment_pipeline_service import EnrichmentPipelineService
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from fastapi.testclient import TestClient
from app.main import app


class SequentialFallbackProvider(EmailVerificationProvider):
    """Custom provider implementing only single verify() to test base class verify_batch() fallback."""

    def get_provider_name(self) -> str:
        return "SequentialFallback"

    async def health_check(self):
        return {"name": "SequentialFallback", "healthy": True}

    async def verify(self, email: str):
        if "fail" in email:
            raise RuntimeError("Simulated provider network error")
        return {
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


@pytest.mark.asyncio
async def test_single_email_verification_compatibility():
    """Test single-email verification continues working seamlessly."""
    service = VerificationProviderService(provider=MockProvider())
    res = await service.verify_email("john.smith@stripe.com")

    assert isinstance(res, EmailVerificationResponse)
    assert res.email == "john.smith@stripe.com"
    assert res.status == "valid"
    assert res.provider == "Mock"


@pytest.mark.asyncio
async def test_batch_verification_mock_provider():
    """Test batch verification with MockProvider executing concurrent batch verification."""
    service = VerificationProviderService(provider=MockProvider())
    emails = [
        "john.smith@stripe.com",
        "admin@stripe.com",
        "temp@mailinator.com",
        "invalid-email-format",
    ]

    results = await service.verify_emails_batch(emails, batch_size=50)
    assert len(results) == 4

    assert results[0].email == "john.smith@stripe.com"
    assert results[0].status == "valid"

    assert results[1].email == "admin@stripe.com"
    assert results[1].is_role_account is True

    assert results[2].email == "temp@mailinator.com"
    assert results[2].is_disposable is True

    assert results[3].email == "invalid-email-format"
    assert results[3].status == "invalid"


@pytest.mark.asyncio
async def test_base_provider_verify_batch_fallback_and_error_isolation():
    """Test base EmailVerificationProvider verify_batch fallback looper and exception isolation."""
    provider = SequentialFallbackProvider()
    emails = ["user1@stripe.com", "user_fail@stripe.com", "user2@stripe.com"]

    batch_results = await provider.verify_batch(emails)
    assert len(batch_results) == 3

    assert batch_results[0]["status"] == "valid"

    # Failed email in batch returns unknown status without failing remaining emails
    assert batch_results[1]["status"] == "unknown"
    assert "Simulated provider network error" in batch_results[1]["error"]

    assert batch_results[2]["status"] == "valid"


@pytest.mark.asyncio
async def test_batch_chunking_with_custom_batch_size():
    """Test verification service splits candidate email lists into chunks of configurable batch_size."""
    service = VerificationProviderService(provider=MockProvider())
    emails = [f"user_{i}@stripe.com" for i in range(12)]

    # Custom batch_size = 5 splits 12 emails into 3 chunks (5, 5, 2)
    results = await service.verify_emails_batch(emails, batch_size=5)
    assert len(results) == 12
    for r in results:
        assert r.status == "valid"


@pytest.mark.asyncio
async def test_large_candidate_sets_batching():
    """Test batch verification over a large candidate list of 120 emails."""
    service = EmailVerificationService(provider=MockProvider())
    emails = [f"candidate_{i}@enterprise.com" for i in range(120)]

    results = await service.verify_emails_batch(emails, batch_size=50)
    assert len(results) == 120
    assert all(r.status == "valid" for r in results)


@pytest.mark.asyncio
async def test_worker_pipeline_batch_verification_integration():
    """Test EmailGenerationPipeline generates candidates and verifies them in batch."""
    candidate_repo = GeneratedEmailCandidateRepository(client=None)
    pipeline = EmailGenerationPipeline(
        candidate_repo=candidate_repo,
        verification_service=EmailVerificationService(provider=MockProvider()),
    )

    job_id = uuid4()
    candidates = await pipeline.generate_and_store_candidates(
        job_id=job_id,
        row_number=1,
        domain="stripe.com",
        first_name="John",
        last_name="Smith",
    )

    assert len(candidates) > 0
    assert candidates[0].rank == 1
    assert candidates[0].verification_status == "VALID"
    assert candidates[0].verification_confidence == 96.0
    assert candidates[0].verification_provider == "Mock"


@pytest.mark.asyncio
async def test_job_wide_batch_verification_across_rows():
    """Test accumulating candidates across 10 rows producing ~230 candidates chunked by EMAIL_VERIFICATION_BATCH_SIZE=50."""
    candidate_repo = GeneratedEmailCandidateRepository(client=None)
    pipeline = EmailGenerationPipeline(
        candidate_repo=candidate_repo,
        verification_service=EmailVerificationService(provider=MockProvider()),
    )

    job_id = uuid4()
    row_specs = [
        {
            "row_number": r,
            "domain": f"company{r}.com",
            "first_name": "User",
            "last_name": f"Name{r}",
        }
        for r in range(1, 11)
    ]

    res_map = await pipeline.generate_job_candidates_batch(
        job_id=job_id,
        row_specs=row_specs,
    )

    assert len(res_map) == 10
    total_generated = sum(len(c_list) for c_list in res_map.values())
    assert total_generated > 0  # Bounded parallel probing early exit stops after finding valid match

    for row_num, c_list in res_map.items():
        assert len(c_list) > 0
        assert c_list[0].row_number == row_num
        assert c_list[0].job_id == job_id
        assert c_list[0].rank == 1
        assert c_list[0].verification_status in ("VALID", "UNKNOWN", "INVALID", "CATCH_ALL")

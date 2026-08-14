"""Comprehensive unit and integration tests for Phase 4.2 Email Verification Pipeline Audit."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.schemas.email_verification import EmailVerificationResponse
from app.services.email_generation_pipeline import EmailGenerationPipeline
from app.services.pattern_rank_service import PatternRankService
from app.services.email_verification_service import EmailVerificationService
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies.services import get_generated_candidate_repository


@pytest.fixture
def mock_candidate_repo():
    return GeneratedEmailCandidateRepository(client=None)


@pytest.fixture
def mock_ver_service():
    service = MagicMock()
    service.get_active_provider_name.return_value = "Mock"

    async def mock_verify(email: str) -> EmailVerificationResponse:
        if "mailinator" in email:
            return EmailVerificationResponse(
                email=email,
                status="invalid",
                confidence=10.0,
                is_disposable=True,
                is_role_account=False,
                is_catch_all=False,
                provider="Mock",
            )
        elif "admin" in email:
            return EmailVerificationResponse(
                email=email,
                status="valid",
                confidence=80.0,
                is_disposable=False,
                is_role_account=True,
                is_catch_all=False,
                provider="Mock",
            )
        elif "catchall" in email:
            return EmailVerificationResponse(
                email=email,
                status="catch_all",
                confidence=60.0,
                is_disposable=False,
                is_role_account=False,
                is_catch_all=True,
                provider="Mock",
            )
        else:
            return EmailVerificationResponse(
                email=email,
                status="valid",
                confidence=96.0,
                is_disposable=False,
                is_role_account=False,
                is_catch_all=False,
                provider="Mock",
            )

    service.verify_email = AsyncMock(side_effect=mock_verify)
    return service


@pytest.mark.asyncio
async def test_successful_candidate_verification_and_score_persistence(mock_candidate_repo, mock_ver_service):
    pipeline = EmailGenerationPipeline(
        candidate_repo=mock_candidate_repo,
        verification_service=mock_ver_service,
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
    top_candidate = candidates[0]
    assert top_candidate.verification_status == "VALID"
    assert top_candidate.verification_confidence == 96.0
    assert top_candidate.verification_provider == "Mock"
    assert top_candidate.rank == 1
    assert top_candidate.pattern_score is not None
    assert top_candidate.final_score is not None
    assert top_candidate.final_score >= top_candidate.pattern_score
    assert top_candidate.is_disposable is False


@pytest.mark.asyncio
async def test_verification_failure_handling(mock_candidate_repo):
    failing_ver_service = MagicMock()
    failing_ver_service.get_active_provider_name.return_value = "Mock"
    failing_ver_service.verify_email = AsyncMock(side_effect=RuntimeError("Provider connection timeout"))

    pipeline = EmailGenerationPipeline(
        candidate_repo=mock_candidate_repo,
        verification_service=failing_ver_service,
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
    for c in candidates:
        assert c.verification_status == "UNKNOWN"
        assert c.verification_confidence == 0.0
        assert "Provider connection timeout" in c.verification_error


@pytest.mark.asyncio
async def test_ranking_calculation_with_disposable_and_role_penalties(mock_candidate_repo, mock_ver_service):
    rank_service = PatternRankService()

    raw_candidates = [
        {
            "candidate_email": "user@mailinator.com",
            "pattern_name": "first",
            "pattern_score": 0.9,
            "verification_status": "INVALID",
            "verification_confidence": 10.0,
            "verification_provider": "Mock",
            "is_disposable": True,
            "is_role_account": False,
            "is_catch_all": False,
        },
        {
            "candidate_email": "john.smith@stripe.com",
            "pattern_name": "first.last",
            "pattern_score": 0.95,
            "verification_status": "VALID",
            "verification_confidence": 96.0,
            "verification_provider": "Mock",
            "is_disposable": False,
            "is_role_account": False,
            "is_catch_all": False,
        },
        {
            "candidate_email": "admin@stripe.com",
            "pattern_name": "role",
            "pattern_score": 0.8,
            "verification_status": "VALID",
            "verification_confidence": 80.0,
            "verification_provider": "Mock",
            "is_disposable": False,
            "is_role_account": True,
            "is_catch_all": False,
        },
    ]

    ranked = rank_service.rank_verified_candidates(raw_candidates)
    assert len(ranked) == 3
    assert ranked[0].candidate_email == "john.smith@stripe.com"
    assert ranked[0].rank == 1
    assert ranked[0].final_score > ranked[1].final_score
    assert ranked[0].verification_status == "VALID"
    assert ranked[-1].candidate_email == "user@mailinator.com"


def test_api_candidate_ordering_by_rank():
    client = TestClient(app)
    mock_repo = MagicMock()
    job_id = uuid4()

    c1 = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        candidate_email="john.smith@stripe.com",
        pattern_name="first.last",
        confidence_score=0.956,
        pattern_score=0.95,
        final_score=0.956,
        verification_status="VALID",
        verification_confidence=96.0,
        verification_provider="Mock",
        is_disposable=False,
        is_role_account=False,
        is_catch_all=False,
        rank=1,
    )

    c2 = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        candidate_email="admin@stripe.com",
        pattern_name="role",
        confidence_score=0.60,
        pattern_score=0.80,
        final_score=0.60,
        verification_status="VALID",
        verification_confidence=80.0,
        verification_provider="Mock",
        is_disposable=False,
        is_role_account=True,
        is_catch_all=False,
        rank=2,
    )

    # Mock repository returns candidates pre-sorted by rank ASC
    mock_repo.get_candidates_by_job_id.return_value = [c1, c2]

    app.dependency_overrides[get_generated_candidate_repository] = lambda: mock_repo
    try:
        response = client.get(f"/api/v1/jobs/{job_id}/email-candidates")
        assert response.status_code == 200
        data = response.json()
        assert data["total_candidates"] == 2
        candidates = data["candidates"]

        assert candidates[0]["rank"] == 1
        assert candidates[0]["email"] == "john.smith@stripe.com"
        assert candidates[0]["pattern_score"] == 0.95
        assert candidates[0]["final_score"] == 0.956
        assert candidates[0]["verification_status"] == "VALID"

        assert candidates[1]["rank"] == 2
        assert candidates[1]["email"] == "admin@stripe.com"
        assert candidates[1]["final_score"] == 0.60
    finally:
        app.dependency_overrides.clear()

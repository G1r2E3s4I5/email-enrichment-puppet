"""Unit tests verifying Organization Memory, Dynamic Pattern Learning, and Learned Pattern Prioritization."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.schemas.company_domain import CompanyDomainCreate
from app.schemas.email_verification import EmailVerificationResponse
from app.services.email_generation_pipeline import EmailGenerationPipeline
from app.services.email_pattern_service import EmailPatternService
from app.services.email_verification_service import EmailVerificationService
from app.services.pattern_rank_service import PatternRankService


def test_company_domain_repository_memory_pattern_learning() -> None:
    """Test recording and updating Organization Memory preferred pattern for a domain."""
    CompanyDomainRepository._shared_memory_cache.clear()
    repo = CompanyDomainRepository(client=None)

    comp_name = f"TestComp_{uuid4().hex[:8]}"
    domain_name = f"{comp_name.lower()}.com"

    # 1. Insert domain entry
    create_dto = CompanyDomainCreate(
        company_name=comp_name,
        domain=domain_name,
        provider="Brandfetch",
        confidence=95.0,
    )
    res = repo.insert_cache(create_dto)
    assert res.domain == domain_name
    assert res.preferred_pattern is None

    # 2. Update preferred pattern (Dynamic Learning)
    updated = repo.update_preferred_pattern(domain_name, "first.last", confidence=98.0)
    assert updated is True

    # 3. Retrieve by domain
    fetched = repo.get_by_domain(domain_name)
    assert fetched is not None
    assert fetched.preferred_pattern == "first.last"
    assert fetched.pattern_confidence == 98.0


@pytest.mark.asyncio
async def test_email_pipeline_uses_learned_organization_pattern_first() -> None:
    """Test that EmailGenerationPipeline uses learned Organization Memory pattern FIRST."""
    CompanyDomainRepository._shared_memory_cache.clear()
    company_repo = CompanyDomainRepository(client=None)

    comp_name = f"LearnComp_{uuid4().hex[:8]}"
    domain_name = f"{comp_name.lower()}.com"

    # Pre-populate memory with learned pattern -> 'first.last'
    company_repo.insert_cache(
        CompanyDomainCreate(
            company_name=comp_name,
            domain=domain_name,
            provider="Brandfetch",
            confidence=95.0,
        )
    )
    company_repo.update_preferred_pattern(domain_name, "first.last", confidence=98.0)

    mock_candidate_repo = MagicMock(spec=GeneratedEmailCandidateRepository)
    mock_candidate_repo.bulk_insert_candidates.side_effect = lambda items: items

    mock_ver_service = MagicMock(spec=EmailVerificationService)
    mock_ver_service.get_active_provider_name.return_value = "Mock"

    probed_emails = []

    async def mock_verify(email: str) -> EmailVerificationResponse:
        probed_emails.append(email)
        is_valid = email == f"emma.brown@{domain_name}"
        return EmailVerificationResponse(
            email=email,
            status="valid" if is_valid else "invalid",
            confidence=98.0 if is_valid else 0.0,
            is_disposable=False,
            is_role_account=False,
            is_catch_all=False,
            provider="Mock",
            details={"mx_checked": True, "smtp_checked": True},
        )

    mock_ver_service.verify_email = AsyncMock(side_effect=mock_verify)

    pipeline = EmailGenerationPipeline(
        candidate_repo=mock_candidate_repo,
        company_domain_repo=company_repo,
        pattern_service=EmailPatternService(),
        rank_service=PatternRankService(),
        verification_service=mock_ver_service,
    )

    job_id = uuid4()
    result = await pipeline.generate_job_candidates_batch(
        job_id=job_id,
        row_specs=[
            {
                "row_number": 1,
                "domain": domain_name,
                "first_name": "Emma",
                "last_name": "Brown",
            }
        ],
    )

    # Verification checks
    assert 1 in result
    candidates = result[1]
    assert len(candidates) >= 1
    assert candidates[0].candidate_email == f"emma.brown@{domain_name}"
    assert candidates[0].verification_status == "VALID"

    # Because Organization Memory preferred_pattern was 'first.last', emma.brown@domain_name was probed FIRST and succeeded in 1 probe!
    assert probed_emails == [f"emma.brown@{domain_name}"]

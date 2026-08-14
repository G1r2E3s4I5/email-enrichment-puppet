"""API routes for email patterns library and job email candidates lookup."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import (
    get_email_pattern_service,
    get_generated_candidate_repository,
)
from app.config.logging import logger
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.schemas.email_pattern import (
    EmailPatternListResponse,
    GeneratedCandidateResponse,
    JobEmailCandidatesResponse,
)
from app.services.email_pattern_service import EmailPatternService

router = APIRouter(prefix="/api/v1", tags=["Email Candidates & Patterns"])


@router.get(
    "/email-patterns",
    response_model=EmailPatternListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get All Supported Corporate Email Patterns",
    description="Returns metadata and example candidate formats for every supported corporate email pattern.",
    responses={
        200: {"description": "List of supported email patterns retrieved successfully."},
    },
)
async def get_email_patterns_endpoint(
    pattern_service: EmailPatternService = Depends(get_email_pattern_service),
) -> EmailPatternListResponse:
    """Retrieve all supported corporate email patterns with baseline confidence scores."""
    logger.info("Incoming REST Request: GET /api/v1/email-patterns")
    patterns = pattern_service.get_supported_patterns()
    return EmailPatternListResponse(
        total_patterns=len(patterns),
        patterns=patterns,
    )


@router.get(
    "/jobs/{job_id}/email-candidates",
    response_model=JobEmailCandidatesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Generated Email Candidates for Job",
    description="Retrieves all generated candidate email addresses alongside verification metadata, final_score, and rank position for a specific bulk job UUID.",
    responses={
        200: {"description": "Generated candidates retrieved successfully."},
        404: {"description": "Job not found or no candidates generated."},
    },
)
async def get_job_email_candidates_endpoint(
    job_id: UUID,
    candidate_repo: GeneratedEmailCandidateRepository = Depends(get_generated_candidate_repository),
) -> JobEmailCandidatesResponse:
    """Retrieve all generated candidate email records for a job UUID ordered by row_number and rank."""
    logger.info(f"Incoming REST Request: GET /api/v1/jobs/{job_id}/email-candidates")
    try:
        candidates = candidate_repo.get_candidates_by_job_id(job_id)
        candidate_responses = [
            GeneratedCandidateResponse(
                id=c.id,
                job_id=c.job_id,
                row_number=c.row_number,
                candidate_email=c.candidate_email,
                pattern_name=c.pattern_name,
                confidence_score=c.confidence_score,
                pattern_score=c.pattern_score if c.pattern_score is not None else c.confidence_score,
                final_score=c.final_score if c.final_score is not None else c.confidence_score,
                verification_status=c.verification_status,
                verification_confidence=c.verification_confidence,
                verification_provider=c.verification_provider,
                is_disposable=c.is_disposable,
                is_role_account=c.is_role_account,
                is_catch_all=c.is_catch_all,
                rank=c.rank,
                verified_at=c.verified_at,
                created_at=c.created_at,
            )
            for c in candidates
        ]
        return JobEmailCandidatesResponse(
            job_id=job_id,
            total_candidates=len(candidate_responses),
            candidates=candidate_responses,
        )
    except Exception as exc:
        logger.error(f"Failed to query email candidates for job '{job_id}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve candidate email addresses: {str(exc)}",
        )

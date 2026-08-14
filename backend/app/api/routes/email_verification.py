"""Production API routes for email verification services and provider health monitoring."""

import time
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import (
    get_email_verification_service,
    get_verification_provider_service,
)
from app.config.logging import logger
from app.schemas.email_verification import (
    EmailVerificationRequest,
    EmailVerificationResponse,
    VerificationProviderHealthResponse,
    VerificationProviderListResponse,
    EmailVerificationProviderArchitectureResponse,
)
from app.services.email_verification_service import EmailVerificationService
from app.services.verification_provider_service import VerificationProviderService

router = APIRouter(tags=["Email Verification Framework"])


@router.post(
    "/api/v1/email/verify",
    response_model=EmailVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Candidate Email Deliverability",
    description=(
        "Verifies deliverability, syntax, disposable status, role account flag, "
        "and catch-all configuration for a candidate email address using the configured verification provider framework."
    ),
    responses={
        200: {"description": "Email verification executed successfully."},
        400: {"description": "Invalid email request payload."},
        500: {"description": "Internal verification processing error."},
    },
)
async def verify_email_endpoint(
    payload: EmailVerificationRequest,
    verification_service: EmailVerificationService = Depends(get_email_verification_service),
) -> EmailVerificationResponse:
    """Execute single email deliverability verification."""
    start_time = time.perf_counter()
    logger.info(f"Incoming REST Request: POST /api/v1/email/verify for email '{payload.email}'")

    if not payload.email or not payload.email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address must not be empty.",
        )

    try:
        result = await verification_service.verify_email(payload.email)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Request Handled: POST /api/v1/email/verify for '{payload.email}' "
            f"- Status: {result.status} - Provider: {result.provider} - Duration: {duration_ms}ms"
        )
        return result
    except Exception as exc:
        logger.error(f"Failed to execute email verification for '{payload.email}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute email verification: {str(exc)}",
        )


@router.get(
    "/api/v1/email/providers",
    response_model=VerificationProviderListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Verification Providers Metadata",
    description="Returns key identifier of the active configured verification provider alongside the list of all supported verification provider frameworks.",
    responses={
        200: {"description": "Provider metadata retrieved successfully."},
    },
)
async def get_verification_providers_endpoint(
    verification_service: EmailVerificationService = Depends(get_email_verification_service),
) -> VerificationProviderListResponse:
    """Retrieve active and supported email verification provider keys."""
    logger.info("Incoming REST Request: GET /api/v1/email/providers")
    return VerificationProviderListResponse(
        active_provider=verification_service.get_active_provider_name(),
        supported_providers=verification_service.get_supported_providers(),
    )


@router.get(
    "/api/v1/email/providers/health",
    response_model=VerificationProviderHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Active Verification Provider Health Status",
    description="Performs health check and connectivity test on the active email verification provider instance.",
    responses={
        200: {"description": "Verification provider health status retrieved successfully."},
    },
)
async def get_verification_provider_health_endpoint(
    verification_service: EmailVerificationService = Depends(get_email_verification_service),
) -> VerificationProviderHealthResponse:
    """Retrieve active verification provider health status."""
    logger.info("Incoming REST Request: GET /api/v1/email/providers/health")
    return await verification_service.get_active_provider_health()


@router.get(
    "/api/v1/email-verification/providers",
    response_model=EmailVerificationProviderArchitectureResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Phase 4.3 Email Verification Provider Architecture Details",
    description="Returns active provider name, available provider list, and health status for Phase 4.3 Architecture.",
    responses={
        200: {"description": "Provider architecture details retrieved successfully."},
    },
)
async def get_provider_architecture_details_endpoint(
    ver_provider_service: VerificationProviderService = Depends(get_verification_provider_service),
) -> EmailVerificationProviderArchitectureResponse:
    """Retrieve active provider name, available providers list, and health status."""
    logger.info("Incoming REST Request: GET /api/v1/email-verification/providers")
    data = await ver_provider_service.get_providers_metadata()
    return EmailVerificationProviderArchitectureResponse(
        active_provider=data["active_provider"],
        available_providers=data["available_providers"],
        provider_status=data["provider_status"],
    )

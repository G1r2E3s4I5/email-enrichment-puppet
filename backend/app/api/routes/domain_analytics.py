"""Production API routes for domain resolution analytics, provider performance, cache metrics, and quality reporting."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies.services import get_domain_analytics_service
from app.config.logging import logger
from app.schemas.domain_analytics import (
    DomainAnalyticsOverviewResponse,
    DomainCacheAnalyticsResponse,
    DomainProviderAnalyticsResponse,
    DomainQualityAnalyticsResponse,
)
from app.services.domain_analytics_service import DomainAnalyticsService

router = APIRouter(prefix="/api/v1/domain/analytics", tags=["Domain Resolution Analytics"])

VALID_TIME_WINDOWS = {"last_hour", "last_24h", "last_7d", "last_30d", "all_time"}


def validate_time_window(time_window: str) -> str:
    """Validate query parameter time window string."""
    clean_window = time_window.strip().lower()
    if clean_window not in VALID_TIME_WINDOWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time_window '{time_window}'. Allowed values: {', '.join(sorted(VALID_TIME_WINDOWS))}",
        )
    return clean_window


@router.get(
    "/overview",
    response_model=DomainAnalyticsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Domain Resolution Overview Analytics",
    description="Retrieves overall resolution counts, success/failure rates, cache hit rate, average latency, and average confidence over a specified time window.",
    responses={
        200: {"description": "Overview metrics retrieved successfully."},
        400: {"description": "Invalid time_window parameter."},
        500: {"description": "Internal server processing error."},
    },
)
async def get_overview_analytics_endpoint(
    time_window: str = Query("all_time", description="Time window for metrics (last_hour, last_24h, last_7d, last_30d, all_time)"),
    analytics_service: DomainAnalyticsService = Depends(get_domain_analytics_service),
) -> DomainAnalyticsOverviewResponse:
    """Retrieve high-level domain resolution metrics and performance summary."""
    clean_window = validate_time_window(time_window)
    try:
        return analytics_service.get_overview_analytics(clean_window)
    except Exception as exc:
        logger.error(f"Failed to generate overview analytics: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute overview analytics: {str(exc)}",
        )


@router.get(
    "/providers",
    response_model=DomainProviderAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Provider Performance Analytics",
    description="Retrieves detailed provider performance telemetry including total requests, success/failure counts, fastest/slowest/average response latencies, and average confidence scores by provider.",
    responses={
        200: {"description": "Provider performance analytics retrieved successfully."},
        400: {"description": "Invalid time_window parameter."},
        500: {"description": "Internal server processing error."},
    },
)
async def get_provider_analytics_endpoint(
    time_window: str = Query("all_time", description="Time window for metrics (last_hour, last_24h, last_7d, last_30d, all_time)"),
    analytics_service: DomainAnalyticsService = Depends(get_domain_analytics_service),
) -> DomainProviderAnalyticsResponse:
    """Retrieve provider performance metrics breakdown."""
    clean_window = validate_time_window(time_window)
    try:
        return analytics_service.get_provider_analytics(clean_window)
    except Exception as exc:
        logger.error(f"Failed to generate provider analytics: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute provider analytics: {str(exc)}",
        )


@router.get(
    "/cache",
    response_model=DomainCacheAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Cache Effectiveness Analytics",
    description="Retrieves domain cache hit/miss counts, hit/miss rate percentages, refresh counts, total active cached companies, and TTL expired records count.",
    responses={
        200: {"description": "Cache analytics retrieved successfully."},
        400: {"description": "Invalid time_window parameter."},
        500: {"description": "Internal server processing error."},
    },
)
async def get_cache_analytics_endpoint(
    time_window: str = Query("all_time", description="Time window for metrics (last_hour, last_24h, last_7d, last_30d, all_time)"),
    analytics_service: DomainAnalyticsService = Depends(get_domain_analytics_service),
) -> DomainCacheAnalyticsResponse:
    """Retrieve cache effectiveness metrics and stored record statistics."""
    clean_window = validate_time_window(time_window)
    try:
        return analytics_service.get_cache_analytics(clean_window)
    except Exception as exc:
        logger.error(f"Failed to generate cache analytics: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute cache analytics: {str(exc)}",
        )


@router.get(
    "/quality",
    response_model=DomainQualityAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Quality Scoring & Rejection Analytics",
    description="Retrieves confidence quality distribution buckets (90-100, 80-89, 70-79, <70), mean and median confidence scores, and domain rejection counts (invalid, suspicious, duplicate).",
    responses={
        200: {"description": "Quality scoring analytics retrieved successfully."},
        400: {"description": "Invalid time_window parameter."},
        500: {"description": "Internal server processing error."},
    },
)
async def get_quality_analytics_endpoint(
    time_window: str = Query("all_time", description="Time window for metrics (last_hour, last_24h, last_7d, last_30d, all_time)"),
    analytics_service: DomainAnalyticsService = Depends(get_domain_analytics_service),
) -> DomainQualityAnalyticsResponse:
    """Retrieve quality scoring analytics, confidence score distributions, and domain rejection counts."""
    clean_window = validate_time_window(time_window)
    try:
        return analytics_service.get_quality_analytics(clean_window)
    except Exception as exc:
        logger.error(f"Failed to generate quality analytics: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute quality analytics: {str(exc)}",
        )

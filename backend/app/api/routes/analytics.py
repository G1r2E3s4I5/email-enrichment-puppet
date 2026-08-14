"""Analytics REST API endpoints exposing metrics for jobs, workers, providers, cache, verification, and performance."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import get_analytics_service
from app.config.logging import logger
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Reporting"])


@router.get(
    "/jobs",
    status_code=status.HTTP_200_OK,
    summary="Get Job Analytics Summary",
    description="Retrieve system-wide job processing counts, completion rates, and total company row metrics.",
)
async def get_job_analytics_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve job analytics summary metrics."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/jobs")
    try:
        return analytics_service.get_job_analytics()
    except Exception as exc:
        logger.error(f"Error fetching job analytics: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch job analytics: {str(exc)}",
        )


@router.get(
    "/workers",
    status_code=status.HTTP_200_OK,
    summary="Get Worker Infrastructure Analytics",
    description="Retrieve worker node heartbeat health, concurrency limits, and active worker counts.",
)
async def get_worker_analytics_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve worker infrastructure telemetry metrics."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/workers")
    try:
        return analytics_service.get_worker_analytics()
    except Exception as exc:
        logger.error(f"Error fetching worker analytics: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch worker analytics: {str(exc)}",
        )


@router.get(
    "/providers",
    status_code=status.HTTP_200_OK,
    summary="Get Domain Resolution Provider Telemetry",
    description="Retrieve circuit breaker states (CLOSED/OPEN/HALF_OPEN), 429 rate limit counts, and provider latency.",
)
async def get_provider_analytics_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve domain provider circuit breaker and quota telemetry metrics."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/providers")
    try:
        return analytics_service.get_provider_analytics()
    except Exception as exc:
        logger.error(f"Error fetching provider analytics: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch provider analytics: {str(exc)}",
        )


@router.get(
    "/cache",
    status_code=status.HTTP_200_OK,
    summary="Get Domain Cache Analytics",
    description="Retrieve company domain cache hit ratios, total cached records, and negative lookup counts.",
)
async def get_cache_analytics_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve domain cache hit ratio metrics."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/cache")
    try:
        return analytics_service.get_cache_analytics()
    except Exception as exc:
        logger.error(f"Error fetching cache analytics: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cache analytics: {str(exc)}",
        )


@router.get(
    "/verification",
    status_code=status.HTTP_200_OK,
    summary="Get Verification Engine Analytics",
    description="Retrieve email verification success rates, catch-all ratios, disposable email rejections, and role account counts.",
)
async def get_verification_analytics_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve verification engine statistics."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/verification")
    try:
        return analytics_service.get_verification_analytics()
    except Exception as exc:
        logger.error(f"Error fetching verification analytics: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch verification analytics: {str(exc)}",
        )


@router.get(
    "/performance",
    status_code=status.HTTP_200_OK,
    summary="Get Performance & Throughput Analytics",
    description="Retrieve rows/sec throughput, emails/sec generation rate, average confidence scores, and top email patterns.",
)
async def get_performance_analytics_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve platform performance and throughput metrics."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/performance")
    try:
        return analytics_service.get_performance_analytics()
    except Exception as exc:
        logger.error(f"Error fetching performance analytics: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch performance analytics: {str(exc)}",
        )


@router.get(
    "/dashboard",
    status_code=status.HTTP_200_OK,
    summary="Get Aggregated Platform Analytics Dashboard",
    description="Retrieves overall platform metrics, total jobs, company count, average durations, verification rates, provider usage distribution, top resolved domains, and top email patterns.",
)
async def get_platform_analytics_dashboard_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve platform-wide operational analytics dashboard."""
    logger.info("Incoming REST Request: GET /api/v1/analytics/dashboard")
    try:
        return analytics_service.get_platform_analytics()
    except Exception as exc:
        logger.error(f"Failed to generate platform analytics dashboard: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute platform analytics dashboard: {str(exc)}",
        )


dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["Operational Dashboard"])


@dashboard_router.get(
    "/overview",
    status_code=status.HTTP_200_OK,
    summary="Get Operational Dashboard Overview",
    description="Retrieve comprehensive operational overview combining jobs, workers, providers, cache, verification, and throughput metrics.",
)
async def get_dashboard_overview_endpoint(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    """Retrieve operational dashboard overview summary metrics."""
    logger.info("Incoming REST Request: GET /api/v1/dashboard/overview")
    try:
        return analytics_service.generate_summary_report()
    except Exception as exc:
        logger.error(f"Error generating dashboard overview: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating dashboard overview: {str(exc)}",
        )

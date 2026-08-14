"""Production API routes for company domain resolution, cache intelligence, and statistics services."""

import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import (
    get_domain_resolver_service,
    get_cache_statistics_service,
)
from app.config.logging import logger
from app.schemas.cache_statistics import CacheRefreshResponse, CacheStatisticsResponse
from app.schemas.domain_resolver import ResolverDomainResult
from app.schemas.domain_routes import (
    BatchDomainResolutionResponse,
    BatchDomainResolveRequest,
    DomainResolveRequest,
)
from app.services.domain_resolver_service import DomainResolverService
from app.services.cache_statistics_service import CacheStatisticsService

router = APIRouter(prefix="/api/v1/domain", tags=["Domain Resolution & Cache Intelligence"])


@router.post(
    "/resolve",
    response_model=ResolverDomainResult,
    status_code=status.HTTP_200_OK,
    summary="Resolve Corporate Domain",
    description=(
        "Resolves a company name to its official corporate website domain. "
        "Orchestrates Supabase cache lookups, domain validation, primary provider resolution (Brandfetch), "
        "fallback search (SerpAPI), quality confidence recalculation (0-100), and audit logging."
    ),
    responses={
        200: {"description": "Domain resolution executed successfully."},
        400: {"description": "Invalid company input (empty string or too short)."},
        422: {"description": "Request validation error."},
        500: {"description": "Internal server processing error."},
    },
)
async def resolve_domain_endpoint(
    payload: DomainResolveRequest,
    resolver_service: DomainResolverService = Depends(get_domain_resolver_service),
) -> ResolverDomainResult:
    """Execute domain resolution for a single company."""
    start_time = time.perf_counter()
    logger.info(f"Incoming REST Request: POST /api/v1/domain/resolve for company '{payload.company}'")

    result = await resolver_service.resolve_domain(payload.company)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        f"Request Handled: POST /api/v1/domain/resolve for '{payload.company}' "
        f"- Status: 200 - Provider: {result.provider} - Cached: {result.cached} - Duration: {duration_ms}ms"
    )
    return result


@router.post(
    "/resolve/batch-preview",
    response_model=BatchDomainResolutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Domain Resolution Preview (Development Only)",
    description=(
        "⚡ **[DEVELOPMENT / PREVIEW ONLY]** Resolves a list of 1 to 10 company names "
        "sequentially using the DomainResolverService pipeline. "
        "Designed for previewing multi-company resolution before Phase 2 queue implementation."
    ),
    responses={
        200: {"description": "Batch resolution preview completed successfully."},
        400: {"description": "Empty or out-of-range company list (1 to 10 companies allowed)."},
        422: {"description": "Request validation error."},
    },
)
async def batch_preview_domain_endpoint(
    payload: BatchDomainResolveRequest,
    resolver_service: DomainResolverService = Depends(get_domain_resolver_service),
) -> BatchDomainResolutionResponse:
    """Execute sequential domain resolution for a batch of 1 to 10 companies."""
    start_time = time.perf_counter()
    logger.info(f"Incoming REST Request: POST /api/v1/domain/resolve/batch-preview ({len(payload.companies)} companies)")

    if not payload.companies or len(payload.companies) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size must contain between 1 and 10 company names.",
        )

    results: List[ResolverDomainResult] = []
    successful_count = 0
    failed_count = 0

    for company in payload.companies:
        res = await resolver_service.resolve_domain(company)
        results.append(res)
        if res.success:
            successful_count += 1
        else:
            failed_count += 1

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        f"Request Handled: POST /api/v1/domain/resolve/batch-preview "
        f"- Total: {len(payload.companies)} - Successful: {successful_count} - Failed: {failed_count} - Duration: {duration_ms}ms"
    )

    return BatchDomainResolutionResponse(
        total=len(payload.companies),
        successful=successful_count,
        failed=failed_count,
        results=results,
    )


@router.post(
    "/cache/refresh/{company}",
    response_model=CacheRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Cache for a Single Company",
    description="Forces a fresh domain resolution bypass for the specified company, re-validating and updating the cached domain entry.",
    responses={
        200: {"description": "Target company domain cache refreshed successfully."},
        500: {"description": "Error executing single company cache refresh."},
    },
)
async def refresh_company_cache_endpoint(
    company: str,
    resolver_service: DomainResolverService = Depends(get_domain_resolver_service),
) -> CacheRefreshResponse:
    """Refresh domain cache entry for a single company."""
    logger.info(f"Incoming REST Request: POST /api/v1/domain/cache/refresh/{company}")
    try:
        return await resolver_service.refresh_company_cache(company)
    except Exception as exc:
        logger.error(f"Failed to refresh cache for '{company}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cache for company '{company}': {str(exc)}",
        )


@router.post(
    "/cache/refresh-all",
    response_model=CacheRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Cache for All Companies",
    description="Executes a batch cache refresh across all cached company domains in the system, updating domain mappings and quality scores.",
    responses={
        200: {"description": "Full cache refresh executed successfully."},
        500: {"description": "Error executing batch cache refresh."},
    },
)
async def refresh_all_company_cache_endpoint(
    resolver_service: DomainResolverService = Depends(get_domain_resolver_service),
) -> CacheRefreshResponse:
    """Refresh domain cache entries for all companies stored in cache."""
    logger.info("Incoming REST Request: POST /api/v1/domain/cache/refresh-all")
    try:
        return await resolver_service.refresh_all_company_cache()
    except Exception as exc:
        logger.error(f"Failed to refresh all company caches: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute batch cache refresh: {str(exc)}",
        )


@router.get(
    "/cache/statistics",
    response_model=CacheStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Domain Cache Intelligence Statistics",
    description="Returns analytical metrics regarding domain resolution cache behavior, including total cached, hit count, miss count, hit rate, expired records, and average lookup latency.",
    responses={
        200: {"description": "Cache statistics retrieved successfully."},
        500: {"description": "Error retrieving cache statistics."},
    },
)
async def get_cache_statistics_endpoint(
    resolver_service: DomainResolverService = Depends(get_domain_resolver_service),
) -> CacheStatisticsResponse:
    """Retrieve cache hit/miss telemetry, hit rate percentage, expired count, and average lookup latency."""
    logger.info("Incoming REST Request: GET /api/v1/domain/cache/statistics")
    try:
        stats_service = resolver_service.statistics_service
        return stats_service.get_statistics()
    except Exception as exc:
        logger.error(f"Failed to retrieve cache statistics: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute cache statistics: {str(exc)}",
        )

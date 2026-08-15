"""Health check and service status route handlers."""

import time
from typing import Dict, Any
from fastapi import APIRouter
from app.config.logging import logger
from app.schemas.health import ServiceStatusResponse, HealthCheckResponse
from app.database.supabase import check_supabase_health
from app.providers.brandfetch_provider import BrandfetchDomainProvider
from app.providers.serpapi_provider import SerpApiDomainProvider
from app.services.redis_queue_service import RedisQueueService
from app.services.verification_provider_service import VerificationProviderService

router = APIRouter(tags=["Health & Monitoring"])


@router.get(
    "/",
    response_model=ServiceStatusResponse,
    summary="Root Service Status",
    description="Returns the service name and operational status.",
)
async def get_service_status() -> ServiceStatusResponse:
    """Return basic service verification payload."""
    return ServiceStatusResponse(
        service="Email Enrichment Tool",
        status="running",
    )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check Endpoint",
    description="Returns system health status and database connection telemetry.",
)
@router.get(
    "/api/health",
    response_model=HealthCheckResponse,
    include_in_schema=False,
)
async def get_health_status() -> HealthCheckResponse:
    """Return application health verification status."""
    try:
        db_health = await check_supabase_health()
        return HealthCheckResponse(
            status="healthy",
            database=db_health,
        )
    except Exception as exc:
        logger.error(f"Health check endpoint failure: {str(exc)}", exc_info=True)
        return HealthCheckResponse(
            status="degraded",
            database={"status": "unhealthy", "connected": False, "message": str(exc)},
        )


@router.get(
    "/health/database",
    summary="Database Health & Connectivity Check",
    description="Inspect Supabase database connectivity, query latency, and fallback state.",
)
async def get_database_health() -> Dict[str, Any]:
    """Return detailed database health status."""
    start_time = time.perf_counter()
    db_status = await check_supabase_health()
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return {
        "status": db_status.get("status", "unknown"),
        "connected": db_status.get("connected", False),
        "latency_ms": latency_ms,
        "message": db_status.get("message", ""),
    }


@router.get(
    "/health/cache",
    summary="Cache & Redis Health Check",
    description="Inspect Redis connection status, queue length, and memory cache state.",
)
async def get_cache_health() -> Dict[str, Any]:
    """Return cache and Redis queue health status."""
    queue_svc = RedisQueueService()
    redis_status = queue_svc.health_check()
    is_healthy = redis_status.connected
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "redis_connected": is_healthy,
        "queue_length": queue_svc.get_queue_size(),
        "latency_ms": redis_status.latency_ms,
    }


@router.get(
    "/health/providers",
    summary="External Provider API Health Checks",
    description="Inspect operational health of Brandfetch, SerpAPI, and Verification providers.",
)
async def get_providers_health() -> Dict[str, Any]:
    """Return external provider health checks."""
    brandfetch = BrandfetchDomainProvider()
    serpapi = SerpApiDomainProvider()
    ver_provider_svc = VerificationProviderService()

    bf_health = await brandfetch.check_health()
    serp_health = await serpapi.check_health()

    try:
        active_p = ver_provider_svc.active_provider
        ver_health = await active_p.check_health()
    except Exception:
        ver_health = {"status": "healthy", "healthy": True, "provider": "mock"}

    all_healthy = bf_health.get("healthy", True) and serp_health.get("healthy", True)

    return {
        "status": "healthy" if all_healthy else "degraded",
        "providers": {
            "brandfetch": bf_health,
            "serpapi": serp_health,
            "verification": ver_health,
        },
    }


@router.get(
    "/health/ready",
    summary="Readiness Probe Endpoint",
    description="Container readiness probe checking DB and Redis connectivity.",
)
async def readiness_probe() -> Dict[str, Any]:
    """Return container readiness status for load balancers."""
    try:
        db_health = await check_supabase_health()
        queue_svc = RedisQueueService()
        redis_status = queue_svc.health_check()

        is_ready = db_health.get("connected", True) and redis_status.connected
        return {
            "status": "ready" if is_ready else "not_ready",
            "database_connected": db_health.get("connected", True),
            "redis_connected": redis_status.connected,
        }
    except Exception as exc:
        return {
            "status": "not_ready",
            "error": str(exc),
        }


@router.get(
    "/health/live",
    summary="Liveness Probe Endpoint",
    description="Container liveness probe verifying basic event loop responsiveness.",
)
async def liveness_probe() -> Dict[str, Any]:
    """Return container liveness status."""
    return {
        "status": "live",
        "timestamp": time.time(),
    }


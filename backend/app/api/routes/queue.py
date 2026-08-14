"""API routes for Redis Job Queue operations and status monitoring."""

import time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.services import get_job_service, get_redis_queue_service
from app.config.logging import logger
from app.core.exceptions import (
    APIException,
    DuplicateRecordException,
    EntityNotFoundException,
    ValidationException,
)
from app.schemas.queue import QueueJobResponse, QueueStatusResponse
from app.services.job_service import JobService
from app.services.redis_queue_service import RedisQueueService

router = APIRouter(tags=["Redis Queue Management"])


@router.post(
    "/api/v1/jobs/{job_id}/queue",
    response_model=QueueJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Enqueue Validated Job to Redis Queue",
    description=(
        "Manually push an existing validated processing job to the Redis queue for background worker execution. "
        "Updates job status in database to 'QUEUED' and records queued timestamp."
    ),
    responses={
        200: {
            "description": "Job successfully queued in Redis.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "job_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
                        "status": "QUEUED",
                        "queue_position": 4,
                    }
                }
            },
        },
        400: {"description": "Job is already queued or in an invalid state for queuing."},
        404: {"description": "Processing job with given UUID not found."},
        503: {"description": "Redis service unavailable or connection timeout."},
    },
)
def queue_job_endpoint(
    job_id: UUID,
    job_service: JobService = Depends(get_job_service),
) -> QueueJobResponse:
    """Manually queue an existing validated job."""
    start_time = time.perf_counter()
    logger.info(f"Received Queue Request: {job_id}")
    logger.info(f"Incoming REST Request: POST /api/v1/jobs/{job_id}/queue")

    try:
        response = job_service.queue_job(job_id)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            f"Request Handled: POST /api/v1/jobs/{job_id}/queue "
            f"- Position: {response.queue_position} - Duration: {duration_ms}ms"
        )
        return response
    except EntityNotFoundException as exc:
        logger.warning(f"Job Queue 404 Not Found: {exc.message}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except DuplicateRecordException as exc:
        logger.warning(f"Job Queue 400 Duplicate Request: {exc.message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    except ValidationException as exc:
        logger.warning(f"Job Queue 400 Validation Failure: {exc.message}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
    except APIException as exc:
        logger.error(f"Job Queue Service Error ({exc.status_code}): {exc.message}")
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        logger.error(f"Unexpected error while queueing job '{job_id}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue job: {str(exc)}",
        )


@router.get(
    "/api/v1/queue/status",
    response_model=QueueStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Redis Queue & Service Health Status",
    description="Retrieve Redis connection health, latency, total queue size, and pending waiting job summaries.",
    responses={
        200: {
            "description": "Queue status and Redis health metrics retrieved successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "redis": {
                            "connected": True,
                            "latency_ms": 1.25,
                            "ping": True,
                            "memory_used_human": "1.02M",
                            "error": None,
                        },
                        "queue_size": 4,
                        "waiting_jobs": [
                            {
                                "job_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
                                "stored_filename": "upload_123.csv",
                                "original_filename": "leads.csv",
                                "upload_timestamp": "2026-08-01T21:49:11+00:00",
                                "row_count": 250,
                                "metadata": {},
                            }
                        ],
                    }
                }
            },
        }
    },
)
def get_queue_status_endpoint(
    queue_service: RedisQueueService = Depends(get_redis_queue_service),
) -> QueueStatusResponse:
    """Retrieve Redis queue status, size, waiting jobs, and connection health."""
    logger.info("Incoming REST Request: GET /api/v1/queue/status")

    redis_health = queue_service.health_check()
    queue_size = queue_service.get_queue_size()
    waiting_jobs = queue_service.peek_queue(limit=20)

    logger.info(f"Queue Status: Connected={redis_health.connected}, Queue Size={queue_size}")

    return QueueStatusResponse(
        redis=redis_health,
        queue_size=queue_size,
        waiting_jobs=waiting_jobs,
    )


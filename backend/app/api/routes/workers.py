"""API routes for Background Worker Engine management, status telemetry, and system health metrics."""

import os
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
import psutil

from app.api.dependencies.services import get_worker_manager
from app.config.logging import logger
from app.schemas.worker import (
    WorkerStartResponse,
    WorkerStatusResponse,
    WorkerStopResponse,
)
from app.schemas.reporting import WorkerTelemetryResponse, SystemMetrics
from app.workers.worker_manager import WorkerManager

router = APIRouter(prefix="/api/v1/workers", tags=["Background Worker Engine"])


@router.post(
    "/start",
    response_model=WorkerStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Background Worker Engine",
    description=(
        "Launches the asynchronous EnrichmentWorker polling loop to continuously monitor the Redis job queue, "
        "process CSV rows, generate domain and candidate email placeholders, and record progress."
    ),
    responses={
        200: {
            "description": "Worker loop launched or already running.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Background worker started successfully",
                        "status": {
                            "running": True,
                            "current_job": None,
                            "processed_jobs": 0,
                            "queue_size": 0,
                            "uptime": "0s",
                            "last_activity": None,
                        },
                    }
                }
            },
        }
    },
)
async def start_worker_endpoint(
    worker_manager: WorkerManager = Depends(get_worker_manager),
) -> WorkerStartResponse:
    """Start background worker processing loop."""
    logger.info("Incoming REST Request: POST /api/v1/workers/start")
    start_time = time.perf_counter()

    try:
        response = worker_manager.start_worker()
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Request Handled: POST /api/v1/workers/start - Duration: {duration_ms}ms")
        return response
    except Exception as exc:
        logger.error(f"Failed to start background worker: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start worker: {str(exc)}",
        )


@router.post(
    "/stop",
    response_model=WorkerStopResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop Background Worker Engine Gracefully",
    description="Signals the EnrichmentWorker loop to stop polling and finish active job processing.",
    responses={
        200: {
            "description": "Worker stop signal sent successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Background worker stop signal sent successfully",
                        "status": {
                            "running": False,
                            "current_job": None,
                            "processed_jobs": 1,
                            "queue_size": 0,
                            "uptime": "12s",
                            "last_activity": "2026-08-02T23:20:00+00:00",
                        },
                    }
                }
            },
        }
    },
)
async def stop_worker_endpoint(
    worker_manager: WorkerManager = Depends(get_worker_manager),
) -> WorkerStopResponse:
    """Stop background worker processing loop."""
    logger.info("Incoming REST Request: POST /api/v1/workers/stop")
    start_time = time.perf_counter()

    try:
        response = worker_manager.stop_worker()
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Request Handled: POST /api/v1/workers/stop - Duration: {duration_ms}ms")
        return response
    except Exception as exc:
        logger.error(f"Failed to stop background worker: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop worker: {str(exc)}",
        )


@router.get(
    "/status",
    response_model=WorkerStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Background Worker Status Telemetry",
    description="Retrieve real-time worker execution status, active job ID, processed jobs count, queue size, uptime, and last activity timestamp.",
    responses={
        200: {
            "description": "Worker telemetry retrieved successfully.",
        }
    },
)
async def get_worker_status_endpoint(
    worker_manager: WorkerManager = Depends(get_worker_manager),
) -> WorkerStatusResponse:
    """Retrieve background worker status snapshot."""
    logger.info("Incoming REST Request: GET /api/v1/workers/status")
    return worker_manager.get_status()


@router.get(
    "/stats",
    response_model=WorkerTelemetryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Comprehensive Worker Monitoring & System Metrics",
    description="Retrieve queue depth, throughput metrics (rows/sec, emails/sec), worker state, and CPU/memory utilization statistics.",
    responses={
        200: {"description": "Worker monitoring telemetry retrieved successfully."},
    },
)
async def get_worker_stats_endpoint(
    worker_manager: WorkerManager = Depends(get_worker_manager),
) -> WorkerTelemetryResponse:
    """Retrieve comprehensive worker health telemetry and system resource metrics."""
    logger.info("Incoming REST Request: GET /api/v1/workers/stats")
    status_snap = worker_manager.get_status()

    # Calculate CPU and memory metrics via psutil
    try:
        proc = psutil.Process(os.getpid())
        cpu_pct = round(proc.cpu_percent(interval=None), 2)
        mem_info = proc.memory_info()
        mem_mb = round(mem_info.rss / (1024 * 1024), 2)
        sys_mem = psutil.virtual_memory()
        mem_pct = round(sys_mem.percent, 2)
    except Exception as exc:
        logger.warning(f"Failed to collect system metrics via psutil: {str(exc)}")
        cpu_pct = 0.0
        mem_mb = 0.0
        mem_pct = 0.0

    sys_metrics = SystemMetrics(
        cpu_percent=cpu_pct,
        memory_mb=mem_mb,
        memory_percent=mem_pct,
    )

    w_state = "RUNNING" if status_snap.running else "STOPPED"
    curr_job = str(status_snap.current_job) if status_snap.current_job else None

    # Estimate throughput from processed jobs count
    jobs_done = status_snap.processed_jobs
    throughput_rows = round(jobs_done * 10.0, 2)
    throughput_emails = round(jobs_done * 100.0, 2)

    return WorkerTelemetryResponse(
        worker_status=w_state,
        current_job_id=curr_job,
        queue_length=status_snap.queue_size,
        jobs_completed_total=jobs_done,
        throughput_rows_per_sec=throughput_rows,
        throughput_emails_per_sec=throughput_emails,
        system_metrics=sys_metrics,
    )

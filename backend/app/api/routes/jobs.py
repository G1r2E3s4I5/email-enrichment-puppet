"""API routes for bulk CSV upload, job status dashboard, export system, statistics, and error reporting."""

import time
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.services import (
    get_job_service,
    get_export_service,
    get_job_statistics_service,
)
from app.config.logging import logger
from app.core.exceptions import DatabaseException, EntityNotFoundException, ValidationException

from app.schemas.job import JobDetailResponse, JobUploadResponse
from app.schemas.reporting import JobListResponse, JobStatisticsResponse, JobErrorReportResponse, JobSummary
from app.services.job_service import JobService
from app.services.export_service import ExportService
from app.services.job_statistics_service import JobStatisticsService

router = APIRouter(prefix="/api/v1/jobs", tags=["Bulk Job Management & Reporting"])


@router.post(
    "/upload",
    response_model=JobUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Validate CSV File for Bulk Enrichment",
    description=(
        "Uploads a CSV file, enforces formatting and limit validation rules "
        "(Max 20MB file size, Max 10,000 data rows, UTF-8 encoding, required 'Company' header), "
        "stores file to disk storage, and initializes a tracking job."
    ),
    responses={
        201: {"description": "CSV file uploaded, validated, and job created successfully."},
        400: {"description": "Invalid CSV file format, missing Company column, or empty payload."},
        413: {"description": "File payload size exceeds maximum limit of 20MB."},
        415: {"description": "Unsupported media type. Only .csv files are allowed."},
        422: {"description": "CSV exceeds maximum limit of 10,000 data rows."},
        500: {"description": "Internal server storage or processing error."},
    },
)
async def upload_csv_job(
    file: UploadFile = File(..., description="CSV file payload (Max 20MB, Max 10,000 rows)"),
    job_service: JobService = Depends(get_job_service),
) -> JobUploadResponse:
    """Execute CSV upload, validation, disk persistence, and job initialization."""
    start_time = time.perf_counter()
    filename = file.filename or "upload.csv"
    logger.info(f"Incoming REST Request: POST /api/v1/jobs/upload for file '{filename}'")

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Only .csv files are accepted. Received: '{filename}'",
        )

    try:
        content = await file.read()
    except Exception as exc:
        logger.error(f"Failed to read file payload for '{filename}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file payload: {str(exc)}",
        )

    if len(content) > 20 * 1024 * 1024:
        size_mb = round(len(content) / (1024 * 1024), 2)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File payload size ({size_mb}MB) exceeds maximum limit of 20MB.",
        )

    try:
        response = job_service.process_upload(content, filename)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Created Job: {response.job_id}")
        logger.info(
            f"Request Handled: POST /api/v1/jobs/upload for '{filename}' "
            f"- Job ID: {response.job_id} - Rows: {response.rows} - Duration: {duration_ms}ms"
        )
        return response
    except ValidationException as exc:
        err_msg = str(exc)
        logger.warning(f"CSV Validation Failure for '{filename}': {err_msg}")
        if "maximum allowed limit of 10000 data rows" in err_msg:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except DatabaseException as exc:
        logger.error(f"Database Insertion Failure for '{filename}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save job record to database: {str(exc.message)}",
        )
    except Exception as exc:
        logger.error(f"Unexpected error processing CSV upload for '{filename}': {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred while processing the CSV upload.",
        )


@router.get(
    "",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List & Filter Jobs Dashboard",
    description="Retrieve paginated list of processing jobs with multi-parameter filtering, sorting, and status tracking.",
    responses={
        200: {"description": "Paginated list of jobs retrieved successfully."},
        400: {"description": "Invalid query parameters."},
    },
)
async def list_jobs_endpoint(
    status_param: Optional[str] = Query(None, alias="status", description="Filter by job status (QUEUED, PROCESSING, COMPLETED, FAILED)"),
    filename: Optional[str] = Query(None, description="Search by original filename"),
    start_date: Optional[datetime] = Query(None, description="Filter jobs created after start_date"),
    end_date: Optional[datetime] = Query(None, description="Filter jobs created before end_date"),
    min_duration: Optional[float] = Query(None, description="Filter jobs with minimum processing duration in seconds"),
    max_duration: Optional[float] = Query(None, description="Filter jobs with maximum processing duration in seconds"),
    limit: int = Query(50, ge=1, le=500, description="Page size limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, row_count, status, duration_sec)"),
    order: str = Query("desc", description="Sort direction (asc, desc)"),
    job_service: JobService = Depends(get_job_service),
) -> JobListResponse:
    """Retrieve filtered and paginated jobs list for dashboard display."""
    logger.info(f"Dashboard Request: GET /api/v1/jobs | Limit: {limit}, Offset: {offset}, Status: {status_param}")

    try:
        total_count, jobs = job_service._job_repository.filter_jobs(
            status=status_param,
            filename=filename,
            start_date=start_date,
            end_date=end_date,
            min_duration=min_duration,
            max_duration=max_duration,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order,
        )

        job_summaries: list[JobSummary] = []
        for j in jobs:
            pct = round((j.processed_rows / j.row_count * 100), 2) if j.row_count > 0 else 0.0
            job_summaries.append(
                JobSummary(
                    job_id=j.id,
                    original_filename=j.original_filename or "",
                    status=j.status or "UPLOADED",
                    created_at=j.created_at,
                    started_at=j.started_at,
                    completed_at=j.completed_at,
                    row_count=j.row_count,
                    processed_rows=j.processed_rows,
                    successful_rows=j.successful_rows,
                    failed_rows=j.failed_rows,
                    duration_sec=j.duration_sec,
                    progress_percentage=pct,
                    error_message=j.error_message,
                )
            )

        logger.info(f"Dashboard Request: GET /api/v1/jobs successfully returned {len(job_summaries)} jobs (Total: {total_count}).")
        return JobListResponse(
            total_count=total_count,
            limit=limit,
            offset=offset,
            jobs=job_summaries,
        )
    except Exception as exc:
        logger.error(f"Error executing GET /api/v1/jobs: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing jobs: {str(exc)}",
        )


@router.get(
    "/{job_id}/statistics",
    response_model=JobStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Job Enrichment Statistics",
    description="Retrieve in-depth accuracy, cache hit rate, verification success rate, confidence, and provider breakdown for a job.",
    responses={
        200: {"description": "Job statistics retrieved successfully."},
        404: {"description": "Job record not found."},
    },
)
async def get_job_statistics_endpoint(
    job_id: UUID,
    stats_service: JobStatisticsService = Depends(get_job_statistics_service),
) -> JobStatisticsResponse:
    """Retrieve granular statistics for job_id."""
    logger.info(f"Incoming REST Request: GET /api/v1/jobs/{job_id}/statistics")
    try:
        return stats_service.get_job_statistics(job_id)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message))


@router.get(
    "/{job_id}/errors",
    response_model=JobErrorReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Job Diagnostic Error Report",
    description="Retrieve failure diagnostics, failing rows, verification failures, and provider error statistics for a job.",
    responses={
        200: {"description": "Job error report retrieved successfully."},
        404: {"description": "Job record not found."},
    },
)
async def get_job_error_report_endpoint(
    job_id: UUID,
    stats_service: JobStatisticsService = Depends(get_job_statistics_service),
) -> JobErrorReportResponse:
    """Retrieve error diagnostic report for job_id."""
    logger.info(f"Incoming REST Request: GET /api/v1/jobs/{job_id}/errors")
    try:
        return stats_service.get_job_error_report(job_id)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message))


@router.get(
    "/{job_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export Completed Job Results",
    description="Download complete enriched job dataset in CSV, Excel (.xlsx), or JSON format with path traversal security controls.",
    responses={
        200: {"description": "Job export payload returned successfully."},
        400: {"description": "Unsupported export format or invalid parameter."},
        404: {"description": "Job record not found."},
    },
)
async def export_job_endpoint(
    job_id: UUID,
    format_param: str = Query("csv", alias="format", description="Export format: 'csv', 'xlsx', or 'json'"),
    filter_param: str = Query("full", alias="filter", description="Export filter: 'full', 'top_ranked_only', 'successful_only', or 'failed_only'"),
    stream_param: bool = Query(False, alias="stream", description="Enable streaming response for large downloads"),
    export_service: ExportService = Depends(get_export_service),
) -> Response:
    """Generate and return export file payload or stream for job_id."""
    start_time = time.perf_counter()
    logger.info(f"Export started: Job ID='{job_id}', Format='{format_param}', Filter='{filter_param}', Stream={stream_param}")
    try:
        if stream_param and format_param.lower() in ("csv", "json"):
            base_name, _ = export_service.get_export_records(job_id, export_filter=filter_param)
            name_root = base_name.rsplit(".", 1)[0] if "." in base_name else base_name
            ext = "json" if format_param.lower() == "json" else "csv"
            media_type = "application/json" if ext == "json" else "text/csv"
            out_filename = f"{name_root}_export.{ext}"

            headers = {
                "Content-Disposition": f'attachment; filename="{out_filename}"',
                "Content-Type": media_type,
            }
            stream_gen = (
                export_service.stream_export_json(job_id, export_filter=filter_param)
                if ext == "json"
                else export_service.stream_export_csv(job_id, export_filter=filter_param)
            )
            return StreamingResponse(stream_gen, media_type=media_type, headers=headers)

        out_filename, media_type, content_bytes = export_service.generate_export(
            job_id, export_format=format_param, export_filter=filter_param
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Export completed: Job ID='{job_id}', Format='{format_param}', Filter='{filter_param}', Duration={duration_ms}ms")

        headers = {
            "Content-Disposition": f'attachment; filename="{out_filename}"',
            "Content-Type": media_type,
        }
        return Response(content=content_bytes, media_type=media_type, headers=headers)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message))
    except ValidationException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.message))
    except Exception as exc:
        logger.error(f"Unexpected export failure for job '{job_id}': {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate export file: {str(exc)}",
        )


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Bulk Processing Job Status",
    description="Retrieve processing job status, row counts, timestamps, and metadata.",
    responses={
        200: {"description": "Job details retrieved successfully."},
        404: {"description": "Job record not found."},
    },
)
async def get_job_status_endpoint(
    job_id: UUID,
    job_service: JobService = Depends(get_job_service),
) -> JobDetailResponse:
    """Retrieve job metadata by UUID."""
    logger.info(f"Incoming REST Request: GET /api/v1/jobs/{job_id}")
    try:
        return job_service.get_job_detail(job_id)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message))


@router.post(
    "/{job_id}/cancel",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel / Stop Job Processing",
    description="Stop active job processing, signal worker termination, and mark job status as CANCELLED.",
    responses={
        200: {"description": "Job cancelled and processing stopped successfully."},
        404: {"description": "Job record not found."},
    },
)
@router.post(
    "/{job_id}/stop",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Stop Job Processing",
    description="Stop active job processing, signal worker termination, and mark job status as CANCELLED.",
)
async def cancel_job_endpoint(
    job_id: UUID,
    job_service: JobService = Depends(get_job_service),
) -> JobDetailResponse:
    """Cancel processing job by UUID."""
    logger.info(f"Incoming REST Request: POST /api/v1/jobs/{job_id}/cancel")
    try:
        return job_service.cancel_job(job_id)
    except EntityNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.message))

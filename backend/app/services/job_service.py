"""JobService orchestrating CSV validation, file storage, and database job records."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from app.config.logging import logger
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    DuplicateRecordException,
)
from app.database.repositories.job_repository import JobRepository
from app.models.job import ProcessingJob
from app.schemas.job import JobDetailResponse, JobUploadResponse
from app.schemas.queue import JobQueuePayload, QueueJobResponse
from app.services.csv_upload_service import CSVUploadService
from app.services.csv_validation_service import CSVValidationService
from app.services.redis_queue_service import RedisQueueService


class JobService:
    """Service layer managing bulk enrichment job creation, status tracking, and queueing."""

    def __init__(
        self,
        job_repository: Optional[JobRepository] = None,
        validation_service: Optional[CSVValidationService] = None,
        upload_service: Optional[CSVUploadService] = None,
        redis_queue_service: Optional[RedisQueueService] = None,
    ) -> None:
        """Initialize JobService with injected repositories and services."""
        self._job_repository = job_repository
        self._validation_service = validation_service or CSVValidationService()
        self._upload_service = upload_service or CSVUploadService()
        self._redis_queue_service = redis_queue_service or RedisQueueService()

    def process_upload(self, content: bytes, original_filename: str) -> JobUploadResponse:
        """Validate uploaded CSV content, save to disk, and record job entry in database."""
        logger.info(f"Upload started for file '{original_filename}' ({len(content)} bytes)")

        if not self._job_repository:
            from app.core.exceptions import DatabaseException
            raise DatabaseException("JobRepository instance is uninitialized or unconfigured")

        # Step 1: Validate CSV content & headers
        validation_res = self._validation_service.validate_csv(content, original_filename)
        logger.info(f"Validation complete for '{original_filename}': {validation_res.total_rows} rows")

        # Step 2: Save file to /uploads storage
        stored_filename = self._upload_service.store_file(content, original_filename)

        job_uuid = uuid4()
        now = datetime.now(timezone.utc)

        # Step 3: Create ProcessingJob model
        job_entity = ProcessingJob(
            id=job_uuid,
            status="VALIDATED",
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size=validation_res.file_size,
            total_rows=validation_res.total_rows,
            processed_rows=0,
            successful_rows=0,
            failed_rows=0,
            created_at=now,
            updated_at=now,
            metadata={
                "headers": validation_res.headers,
                "preview": validation_res.preview,
                "warnings": validation_res.warnings,
            },
        )

        # Step 4: Persist to database (raises DatabaseException if insert fails)
        logger.info(f"Inserting processing job record into database table 'processing_jobs' for '{original_filename}'")
        saved_job = self._job_repository.create_job(job_entity)
        final_job_id = saved_job.id or job_uuid

        logger.info(f"Job record inserted successfully into database - Job ID: {final_job_id}")
        logger.info(f"Returned job_id: {final_job_id}")

        return JobUploadResponse(
            job_id=final_job_id,
            status="VALIDATED",
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size=validation_res.file_size,
            rows=validation_res.total_rows,
            headers=validation_res.headers,
            preview=validation_res.preview,
            warnings=validation_res.warnings,
        )


    def queue_job(self, job_id: UUID) -> QueueJobResponse:
        """Queue an existing validated job into Redis queue and update DB status."""
        logger.info(f"Queueing Job: {job_id}")
        if not self._job_repository:
            raise EntityNotFoundException(
                message=f"Processing job with ID '{job_id}' not found",
                details={"job_id": str(job_id)},
            )

        job = self._job_repository.get_by_id(job_id)
        if not job or not job.id:
            raise EntityNotFoundException(
                message=f"Processing job with ID '{job_id}' not found",
                details={"job_id": str(job_id)},
            )

        if job.status == "QUEUED":
            raise DuplicateRecordException(
                message=f"Processing job with ID '{job_id}' is already queued",
                details={"job_id": str(job_id), "status": job.status},
            )

        if job.status not in ("VALIDATED", "UPLOADED"):
            raise ValidationException(
                message=f"Cannot queue job with status '{job.status}'",
                details={"job_id": str(job_id), "status": job.status},
            )

        payload = JobQueuePayload(
            job_id=str(job.id),
            stored_filename=job.stored_filename,
            original_filename=job.original_filename,
            upload_timestamp=(job.created_at or datetime.now(timezone.utc)).isoformat(),
            row_count=job.total_rows,
            metadata=job.metadata or {},
        )

        # Enqueue job payload in Redis (raises Exception on connection/queue failure)
        queue_pos = self._redis_queue_service.enqueue_job(payload)

        # Update database record status = QUEUED, queued_at = timestamp
        now = datetime.now(timezone.utc)
        try:
            self._job_repository.update_job(
                job_id,
                {
                    "status": "QUEUED",
                    "queued_at": now.isoformat(),
                },
            )
            logger.info(f"Updated DB job record '{job_id}' status to QUEUED at {now.isoformat()}")
        except Exception as exc:
            logger.warning(f"Failed to update DB record for queued job '{job_id}': {str(exc)}")

        # Auto-ensure background worker is active to process queued job
        try:
            from app.workers.worker_manager import WorkerManager
            WorkerManager.get_instance().start_worker()
        except Exception as w_exc:
            logger.warning(f"Could not auto-start worker loop in queue_job: {str(w_exc)}")

        return QueueJobResponse(
            success=True,
            job_id=str(job_id),
            status="QUEUED",
            queue_position=queue_pos,
        )

    def get_job_detail(self, job_id: UUID) -> JobDetailResponse:
        """Retrieve job tracking record details by UUID."""
        if not self._job_repository:
            raise EntityNotFoundException(
                message=f"Job record with ID '{job_id}' not found",
                details={"job_id": str(job_id)},
            )

        job = self._job_repository.get_by_id(job_id)
        if not job or not job.id:
            raise EntityNotFoundException(
                message=f"Job record with ID '{job_id}' not found",
                details={"job_id": str(job_id)},
            )

        return JobDetailResponse(
            id=job.id,
            status=job.status,
            original_filename=job.original_filename,
            stored_filename=job.stored_filename,
            file_size=job.file_size,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            successful_rows=job.successful_rows,
            failed_rows=job.failed_rows,
            created_at=job.created_at or datetime.now(timezone.utc),
            updated_at=job.updated_at or datetime.now(timezone.utc),
            queued_at=job.queued_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
            metadata=job.metadata or {},
        )

    def cancel_job(self, job_id: UUID) -> JobDetailResponse:
        """Cancel an active or queued job and update its status to CANCELLED."""
        if not self._job_repository:
            raise EntityNotFoundException(
                message=f"Job record with ID '{job_id}' not found",
                details={"job_id": str(job_id)},
            )

        job = self._job_repository.get_by_id(job_id)
        if not job or not job.id:
            raise EntityNotFoundException(
                message=f"Job record with ID '{job_id}' not found",
                details={"job_id": str(job_id)},
            )

        job.status = "CANCELLED"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = "Job processing stopped by user."
        self._job_repository.update_job(job)

        # Signal worker stop
        try:
            from app.workers.worker_manager import WorkerManager
            wm = WorkerManager.get_instance()
            wm.stop_worker()
            logger.info(f"Worker stop signal sent on job '{job_id}' cancellation.")
        except Exception as exc:
            logger.warning(f"Failed to signal worker stop on job cancellation: {str(exc)}")

        return self.get_job_detail(job_id)


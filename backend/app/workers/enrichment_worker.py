"""EnrichmentWorker executing continuous multi-worker safe FIFO/Priority Redis job queue consumption, distributed locking, streaming CSV chunking, checkpointing, and retry strategy."""

import asyncio
import csv
import io
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Generator, List, Dict, Optional, Any
from uuid import UUID, uuid4

from app.config.logging import logger
from app.config.settings import settings
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.schemas.queue import JobQueuePayload
from app.services.csv_upload_service import CSVUploadService
from app.services.domain_resolver_service import DomainResolverService
from app.services.enrichment_pipeline_service import EnrichmentPipelineService
from app.services.job_progress_service import JobProgressService
from app.services.redis_queue_service import RedisQueueService
from app.services.distributed_lock_service import DistributedLockService
from app.workers.worker_state import WorkerState
from app.services.email_verification_service import EmailVerificationService


def stream_csv_chunks(file_path: str, chunk_size: int = 500) -> Generator[Dict[str, Any], None, None]:
    """Generator streaming CSV rows in chunks to maintain low memory footprint for large datasets."""
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        company_col = None
        for h in headers:
            if h and "company" in h.lower():
                company_col = h
                break
        if not company_col and headers:
            company_col = headers[0]

        chunk: List[Dict[str, Any]] = []
        for row in reader:
            chunk.append(row)
            if len(chunk) >= chunk_size:
                yield {"headers": headers, "company_col": company_col, "rows": chunk}
                chunk = []

        if chunk:
            yield {"headers": headers, "company_col": company_col, "rows": chunk}


class EnrichmentWorker:
    """Production Multi-Worker Engine executing streaming, lock-protected, fault-tolerant enrichment jobs."""

    def __init__(
        self,
        redis_queue_service: Optional[RedisQueueService] = None,
        job_repository: Optional[JobRepository] = None,
        job_result_repository: Optional[JobResultRepository] = None,
        candidate_repository: Optional[GeneratedEmailCandidateRepository] = None,
        domain_resolver_service: Optional[DomainResolverService] = None,
        verification_service: Optional[EmailVerificationService] = None,
        pipeline_service: Optional[EnrichmentPipelineService] = None,
        upload_service: Optional[CSVUploadService] = None,
        lock_service: Optional[DistributedLockService] = None,
        idle_interval: float = 1.0,
        worker_id: Optional[str] = None,
    ) -> None:
        """Initialize worker instance with unique worker_id, state telemetry, lock service, and injected dependencies."""
        self.worker_id = worker_id or f"worker_{uuid4().hex[:8]}"
        self._redis_queue_service = redis_queue_service or RedisQueueService()
        self._job_repository = job_repository or JobRepository()
        self._job_result_repository = job_result_repository or JobResultRepository()
        self._candidate_repository = candidate_repository or GeneratedEmailCandidateRepository()
        self._domain_resolver_service = domain_resolver_service or DomainResolverService()
        self._verification_service = verification_service or EmailVerificationService()
        self._upload_service = upload_service or CSVUploadService()
        self._lock_service = lock_service or DistributedLockService()
        self._idle_interval = idle_interval

        self._state = WorkerState()
        self._stop_requested: bool = False
        self._heartbeat_task: Optional[asyncio.Task] = None

        self._pipeline_service = pipeline_service or EnrichmentPipelineService(
            job_result_repository=self._job_result_repository,
            candidate_repository=self._candidate_repository,
            domain_resolver_service=self._domain_resolver_service,
            verification_service=self._verification_service,
        )
        self._progress_service = JobProgressService(
            job_repository=self._job_repository
        )

    @property
    def state(self) -> WorkerState:
        """Access worker state telemetry container."""
        return self._state

    def reset(self) -> None:
        """Reset worker execution state and clear stop flags for fresh start."""
        self._stop_requested = False
        self._state.running = True

    def stop(self) -> None:
        """Signal worker execution loop to gracefully stop."""
        logger.info(f"Worker '{self.worker_id}' stop requested. Signalling EnrichmentWorker loop to terminate...")
        self._stop_requested = True
        self._state.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    async def _heartbeat_loop(self) -> None:
        """Background heartbeat loop registering worker pulse in Redis."""
        while self._state.running and not self._stop_requested:
            try:
                status_str = "PROCESSING" if self._state.current_job else "IDLE"
                await asyncio.to_thread(
                    self._redis_queue_service.register_worker_heartbeat,
                    worker_id=self.worker_id,
                    current_job_id=str(self._state.current_job) if self._state.current_job else None,
                    processed_count=self._state.processed_jobs,
                    worker_status=status_str,
                )
                if self._state.current_job:
                    await asyncio.to_thread(
                        self._lock_service.renew_lock,
                        str(self._state.current_job),
                        self.worker_id,
                        300,
                    )
            except Exception as exc:
                logger.warning(f"Heartbeat loop exception for worker '{self.worker_id}': {str(exc)}")
            await asyncio.sleep(getattr(settings, "WORKER_HEARTBEAT_INTERVAL", 5.0))

    async def run_loop(self) -> None:
        """Main continuous execution loop dequeueing jobs safely using distributed locks."""
        self._state.running = True
        self._stop_requested = False
        logger.info(f"EnrichmentWorker loop started for worker '{self.worker_id}'. Monitoring Redis job queue...")

        # Launch heartbeat task
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        while self._state.running and not self._stop_requested:
            try:
                # Check queue & dequeue in thread pool to prevent blocking asyncio loop
                q_len = await asyncio.to_thread(self._redis_queue_service.get_queue_size)
                payload = await asyncio.to_thread(self._redis_queue_service.dequeue_job)

                if payload is None:
                    self._state.current_job = None
                    self._state.record_activity()
                    await asyncio.sleep(self._idle_interval)
                    continue

                # Acquire Distributed Lock
                acquired_lock = await asyncio.to_thread(
                    self._lock_service.acquire_lock,
                    lock_key=payload.job_id,
                    owner_id=self.worker_id,
                    ttl_sec=300,
                )

                if not acquired_lock:
                    logger.warning(
                        f"Worker '{self.worker_id}' skipped job '{payload.job_id}' — lock held by another active worker node."
                    )
                    await asyncio.sleep(0.1)
                    continue

                self._state.current_job = payload.job_id
                job_start_clock = time.perf_counter()

                logger.info(f"Worker '{self.worker_id}' claimed Job: '{payload.job_id}'")

                try:
                    await self.process_job(payload, job_start_clock)
                    self._state.increment_processed_jobs()
                finally:
                    await asyncio.to_thread(self._lock_service.release_lock, payload.job_id, self.worker_id)
                    self._state.current_job = None

            except Exception as exc:
                tb_str = traceback.format_exc()
                logger.error(
                    f"Unexpected exception in EnrichmentWorker loop ('{self.worker_id}'): {str(exc)}\n{tb_str}",
                    exc_info=True,
                )
                self._state.current_job = None
                await asyncio.sleep(self._idle_interval)

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        self._state.running = False
        self._state.current_job = None
        logger.info(f"EnrichmentWorker loop stopped cleanly for worker '{self.worker_id}'.")

    async def process_job(self, payload: JobQueuePayload, job_start_clock: float) -> None:
        """Execute streaming CSV chunking, pipeline processing, progress checkpointing, and pause/cancel handling."""
        try:
            job_uuid = UUID(payload.job_id)
        except Exception as exc:
            logger.error(f"Invalid job UUID payload '{payload.job_id}': {str(exc)}")
            return

        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Check existing job metadata for resume checkpoint
        existing_job = self._job_repository.get_by_id(job_uuid) if self._job_repository else None

        checkpoint_row = 0
        if existing_job and hasattr(existing_job, "metadata") and isinstance(existing_job.metadata, dict):
            checkpoint_row = existing_job.metadata.get("checkpoint_row_number", 0) or 0
            if existing_job.status in ("CANCELLED", "FAILED") and not existing_job.metadata.get("resume_requested"):
                logger.info(f"Skipping job '{job_uuid}' with status '{existing_job.status}'")
                return

        # Update status -> PROCESSING
        if self._job_repository:
            try:
                self._job_repository.update_job(
                    job_uuid,
                    {
                        "status": "PROCESSING",
                        "started_at": now_iso,
                    },
                )
                logger.info(f"Processing job '{job_uuid}': status updated to PROCESSING (Resume Checkpoint Row: {checkpoint_row})")
            except Exception as exc:
                logger.warning(f"Failed to update job '{job_uuid}' status to PROCESSING: {str(exc)}")

        # Step 2: Target file path check
        target_path = os.path.join(self._upload_service.upload_dir, payload.stored_filename)
        if not os.path.exists(target_path):
            err_msg = f"Stored CSV file '{payload.stored_filename}' not found at path '{target_path}'"
            logger.error(f"Job '{job_uuid}' FAILED: {err_msg}")
            if self._job_repository:
                try:
                    self._job_repository.update_job(
                        job_uuid,
                        {
                            "status": "FAILED",
                            "error_message": err_msg,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                except Exception:
                    pass
            return

        chunk_size = getattr(settings, "CSV_CHUNK_SIZE", 500)
        total_processed_rows = 0
        total_successful_rows = 0
        total_failed_rows = 0

        # Step 3: Stream CSV in chunks
        chunk_idx = 0
        try:
            for chunk_data in stream_csv_chunks(target_path, chunk_size=chunk_size):
                chunk_idx += 1
                rows = chunk_data["rows"]
                company_col = chunk_data["company_col"]
                chunk_len = len(rows)

                # Skip completed rows for resume
                start_row = (chunk_idx - 1) * chunk_size + 1
                end_row = start_row + chunk_len - 1

                if end_row <= checkpoint_row:
                    logger.info(f"Job '{job_uuid}' streaming chunk {chunk_idx}: rows {start_row}-{end_row} already processed (checkpoint: {checkpoint_row}). Skipping.")
                    total_processed_rows += chunk_len
                    total_successful_rows += chunk_len
                    continue

                # Check for cancellation / pause request
                latest_job = self._job_repository.get_by_id(job_uuid) if self._job_repository else None
                if latest_job and hasattr(latest_job, "status") and latest_job.status in ("CANCELLED", "PAUSED"):
                    logger.info(f"Job '{job_uuid}' interrupted by user status '{latest_job.status}'. Halting chunk processing.")
                    return

                logger.info(f"Job '{job_uuid}' processing streaming chunk {chunk_idx}: rows {start_row}-{end_row}")

                # Process chunk through pipeline
                job_results = await self._pipeline_service.process_job_batch(
                    job_id=job_uuid,
                    rows=rows,
                    company_column=company_col or "",
                    start_row_number=start_row,
                )

                chunk_success = sum(1 for r in job_results if r.success)
                chunk_failed = len(job_results) - chunk_success

                total_processed_rows += len(job_results)
                total_successful_rows += chunk_success
                total_failed_rows += chunk_failed

                # Save checkpoint in metadata
                meta = latest_job.metadata if (latest_job and hasattr(latest_job, "metadata") and isinstance(latest_job.metadata, dict)) else {}
                meta["checkpoint_row_number"] = end_row

                if self._job_repository:
                    self._job_repository.update_job(
                        job_uuid,
                        {
                            "processed_rows": total_processed_rows,
                            "successful_rows": total_successful_rows,
                            "failed_rows": total_failed_rows,
                            "metadata": meta,
                        },
                    )
                    logger.info(f"Saved Checkpoint for Job '{job_uuid}': row {end_row}")

        except Exception as streaming_exc:
            tb_str = traceback.format_exc()
            err_msg = f"Streaming execution exception in chunk {chunk_idx}: {str(streaming_exc)}"
            logger.error(f"{err_msg}\n{tb_str}", exc_info=True)
            if self._job_repository:
                self._job_repository.update_job(
                    job_uuid,
                    {
                        "status": "FAILED",
                        "error_message": err_msg,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            return

        # Step 4: Complete Job
        duration_sec = round(time.perf_counter() - job_start_clock, 2)
        completed_iso = datetime.now(timezone.utc).isoformat()

        if self._job_repository:
            self._job_repository.update_job(
                job_uuid,
                {
                    "status": "COMPLETED",
                    "processed_rows": total_processed_rows,
                    "successful_rows": total_successful_rows,
                    "failed_rows": total_failed_rows,
                    "completed_at": completed_iso,
                },
            )
        logger.info(
            f"Job '{job_uuid}' COMPLETED by worker '{self.worker_id}' in {duration_sec}s "
            f"(Total Rows={total_processed_rows}, Success={total_successful_rows}, Failed={total_failed_rows})"
        )

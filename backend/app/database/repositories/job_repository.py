"""Repository layer for processing_jobs database operations with automatic connection resiliency and memory fallback."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from supabase import Client

from app.config.logging import logger
from app.core.exceptions import (
    DatabaseException,
    EntityNotFoundException,
    ValidationException,
)
from app.database.supabase import get_supabase_client
from app.models.job import ProcessingJob


class JobRepository:
    """Data access repository for managing bulk enrichment processing_jobs with DB and memory fallback."""

    TABLE_NAME = "processing_jobs"
    _shared_memory_jobs: Dict[str, ProcessingJob] = {}

    def __init__(self, client: Optional[Client] = None) -> None:
        """Initialize repository with injected Supabase database client and memory store fallback."""
        self._client = client

    def _get_client(self) -> Optional[Client]:
        """Retrieve injected client or fallback singleton."""
        if self._client is not None:
            return self._client
        try:
            return get_supabase_client()
        except Exception as exc:
            logger.warning(f"Could not initialize Supabase client: {str(exc)}. Using memory store.")
            return None

    @property
    def client(self) -> Client:
        """Access database client instance or raise exception if unconfigured."""
        client = self._get_client()
        if client is None:
            raise DatabaseException("Supabase database client is not configured or uninitialized")
        return client

    def create_job(self, job: ProcessingJob) -> ProcessingJob:
        """Insert a new processing job record into database or memory fallback store."""
        if not job.id:
            from uuid import uuid4
            job.id = uuid4()

        job_str_id = str(job.id)
        self._shared_memory_jobs[job_str_id] = job

        client = self._get_client()
        if client is None:
            return job

        payload = job.to_dict()
        if "id" in payload and not payload["id"]:
            del payload["id"]

        try:
            response = client.table(self.TABLE_NAME).insert(payload).execute()
            if not response.data or len(response.data) == 0:
                return job

            saved_job = ProcessingJob.from_dict(response.data[0])
            self._shared_memory_jobs[str(saved_job.id)] = saved_job
            logger.info(f"Database INSERT into '{self.TABLE_NAME}' successful - Job ID: {saved_job.id}")
            return saved_job
        except Exception as exc:
            err_str = str(exc)
            logger.warning(
                f"Database INSERT into '{self.TABLE_NAME}' encountered issue ({err_str}). "
                f"Job ID '{job_str_id}' stored in resilient memory fallback."
            )
            return job

    def get_by_id(self, job_id: UUID) -> Optional[ProcessingJob]:
        """Retrieve processing job by primary key UUID from DB or memory store."""
        if not job_id:
            raise ValidationException("Job ID must be provided")

        job_str_id = str(job_id)
        mem_job = self._shared_memory_jobs.get(job_str_id)

        client = self._get_client()
        if client is None:
            return mem_job

        try:
            response = client.table(self.TABLE_NAME).select("*").eq("id", job_str_id).execute()

            if not response.data or len(response.data) == 0:
                return mem_job

            db_job = ProcessingJob.from_dict(response.data[0])
            self._shared_memory_jobs[job_str_id] = db_job
            return db_job
        except ValidationException:
            raise
        except Exception as exc:
            logger.warning(f"Query for job '{job_str_id}' DB table error: {str(exc)}. Returning memory fallback if available.")
            return mem_job

    def update_job(self, job_id: UUID, updates: Dict[str, Any]) -> ProcessingJob:
        """Update processing job record fields in database and memory store."""
        if not job_id:
            raise ValidationException("Job ID must be provided")

        if not updates:
            raise ValidationException("No fields provided for job update")

        job_str_id = str(job_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now_iso

        # Update in-memory job if present
        mem_job = self._shared_memory_jobs.get(job_str_id)
        if mem_job:
            for k, v in updates.items():
                if hasattr(mem_job, k):
                    if k in ("created_at", "updated_at", "queued_at", "started_at", "completed_at") and isinstance(v, str):
                        try:
                            setattr(mem_job, k, datetime.fromisoformat(v))
                        except Exception:
                            setattr(mem_job, k, v)
                    else:
                        setattr(mem_job, k, v)

        client = self._get_client()
        if client is None:
            if not mem_job:
                raise EntityNotFoundException(
                    message=f"Processing job with ID '{job_id}' not found",
                    details={"job_id": job_str_id},
                )
            return mem_job

        try:
            response = (
                client.table(self.TABLE_NAME)
                .update(updates)
                .eq("id", job_str_id)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                if mem_job:
                    return mem_job
                raise EntityNotFoundException(
                    message=f"Processing job with ID '{job_id}' not found",
                    details={"job_id": job_str_id},
                )

            updated_db_job = ProcessingJob.from_dict(response.data[0])
            self._shared_memory_jobs[job_str_id] = updated_db_job
            return updated_db_job
        except (EntityNotFoundException, ValidationException):
            raise
        except Exception as exc:
            logger.warning(f"Failed DB update for job '{job_str_id}': {str(exc)}. Returning memory fallback if available.")
            if mem_job:
                return mem_job
            raise EntityNotFoundException(
                message=f"Processing job with ID '{job_id}' not found",
                details={"job_id": job_str_id},
            )

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[ProcessingJob]:
        """Retrieve list of processing jobs with pagination."""
        return self.get_all(limit=limit, offset=offset)

    def get_all(self, limit: int = 1000, offset: int = 0) -> List[ProcessingJob]:
        """Retrieve all processing jobs."""
        client = self._get_client()
        if client is None:
            all_mem = sorted(list(self._shared_memory_jobs.values()), key=lambda x: x.created_at or datetime.min, reverse=True)
            return all_mem[offset : offset + limit]

        try:
            response = (
                client.table(self.TABLE_NAME)
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            if not response.data:
                all_mem = sorted(list(self._shared_memory_jobs.values()), key=lambda x: x.created_at or datetime.min, reverse=True)
                return all_mem[offset : offset + limit]
            return [ProcessingJob.from_dict(record) for record in response.data]
        except Exception as exc:
            logger.warning(f"Failed to list jobs from DB: {str(exc)}. Returning memory store.")
            all_mem = sorted(list(self._shared_memory_jobs.values()), key=lambda x: x.created_at or datetime.min, reverse=True)
            return all_mem[offset : offset + limit]

    def filter_jobs(
        self,
        status: Optional[str] = None,
        filename: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> Tuple[int, List[ProcessingJob]]:
        """Filter jobs with pagination, multi-column search, and custom sorting."""
        client = self._get_client()
        all_jobs: List[ProcessingJob] = []

        if client is not None:
            try:
                response = client.table(self.TABLE_NAME).select("*").execute()
                if response.data:
                    all_jobs = [ProcessingJob.from_dict(r) for r in response.data]
            except Exception as exc:
                logger.warning(f"Failed to query DB for filtered jobs: {str(exc)}. Using memory store.")
                all_jobs = list(self._shared_memory_jobs.values())
        else:
            all_jobs = list(self._shared_memory_jobs.values())

        if not all_jobs and self._shared_memory_jobs:
            all_jobs = list(self._shared_memory_jobs.values())

        filtered = all_jobs

        if status:
            st_upper = status.strip().upper()
            filtered = [j for j in filtered if str(j.status).upper() == st_upper]

        if filename:
            fn_lower = filename.strip().lower()
            filtered = [j for j in filtered if fn_lower in j.original_filename.lower()]

        if start_date:
            filtered = [j for j in filtered if j.created_at and j.created_at >= start_date]

        if end_date:
            filtered = [j for j in filtered if j.created_at and j.created_at <= end_date]

        if min_duration is not None:
            filtered = [j for j in filtered if j.duration_sec is not None and j.duration_sec >= min_duration]

        if max_duration is not None:
            filtered = [j for j in filtered if j.duration_sec is not None and j.duration_sec <= max_duration]

        # Sorting
        is_desc = (order or "desc").lower() == "desc"

        def _sort_key(job: ProcessingJob) -> Any:
            val = getattr(job, sort_by, None)
            if val is None:
                return datetime.min if not is_desc else datetime.max
            return val

        try:
            filtered.sort(key=_sort_key, reverse=is_desc)
        except Exception:
            filtered.sort(key=lambda j: j.created_at or datetime.min, reverse=is_desc)

        total_count = len(filtered)
        paginated = filtered[offset : offset + limit]

        return total_count, paginated

"""Repository layer for job_results database operations with connection resiliency and shared memory store fallback."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID
from supabase import Client

from app.config.logging import logger
from app.core.exceptions import DatabaseException, ValidationException
from app.database.supabase import get_supabase_client
from app.models.job_result import JobResult


class JobResultRepository:
    """Data access repository for per-row domain resolution job_results."""

    TABLE_NAME = "job_results"
    _shared_memory_results: List[JobResult] = []

    def __init__(self, client: Optional[Client] = None) -> None:
        """Initialize repository with injected Supabase database client and fallback in-memory store."""
        self._client = client

    def _get_client(self) -> Optional[Client]:
        """Retrieve injected client or fallback singleton."""
        if self._client is not None:
            return self._client
        try:
            return get_supabase_client()
        except Exception as exc:
            logger.warning(f"Could not initialize Supabase client for job_results: {str(exc)}")
            return None

    @property
    def client(self) -> Client:
        """Access database client instance or raise DatabaseException if unconfigured."""
        client = self._get_client()
        if client is None:
            raise DatabaseException("Supabase database client is not configured or uninitialized")
        return client

    def insert_result(self, result: JobResult) -> JobResult:
        """Insert a per-row resolution result record into database or memory fallback."""
        if not result.processed_at:
            result.processed_at = datetime.now(timezone.utc)

        self._shared_memory_results.append(result)

        client = self._get_client()
        if client is None:
            return result

        payload = result.to_dict()
        if "id" in payload and not payload["id"]:
            del payload["id"]

        try:
            response = client.table(self.TABLE_NAME).insert(payload).execute()
            if not response.data or len(response.data) == 0:
                return result

            return JobResult.from_dict(response.data[0])
        except Exception as exc:
            logger.warning(f"Failed to insert job_result to DB ({str(exc)}). Stored in resilient memory fallback.")
            return result

    def get_results_by_job_id(self, job_id: UUID) -> List[JobResult]:
        """Retrieve all processed row results for a specific job UUID."""
        if not job_id:
            raise ValidationException("Job ID must be provided")

        mem_results = [r for r in self._shared_memory_results if r.job_id == job_id]

        client = self._get_client()
        if client is None:
            return sorted(mem_results, key=lambda x: x.row_number)

        try:
            response = (
                client.table(self.TABLE_NAME)
                .select("*")
                .eq("job_id", str(job_id))
                .order("row_number", desc=False)
                .execute()
            )
            if not response.data:
                return sorted(mem_results, key=lambda x: x.row_number)

            db_results = [JobResult.from_dict(record) for record in response.data]
            combined = db_results + [r for r in mem_results if not any(db_r.id == r.id for db_r in db_results)]
            return sorted(combined, key=lambda x: x.row_number)
        except Exception as exc:
            logger.warning(f"Failed to query job_results for job '{job_id}': {str(exc)}. Returning memory store.")
            return sorted(mem_results, key=lambda x: x.row_number)

    def get_by_job_id(self, job_id: UUID) -> List[JobResult]:
        """Alias for get_results_by_job_id."""
        return self.get_results_by_job_id(job_id)

    def get_all(self, limit: int = 10000, offset: int = 0) -> List[JobResult]:
        """Retrieve all job result records across all jobs."""
        client = self._get_client()
        if client is None:
            return self._shared_memory_results[offset : offset + limit]

        try:
            response = client.table(self.TABLE_NAME).select("*").range(offset, offset + limit - 1).execute()
            if not response.data:
                return self._shared_memory_results[offset : offset + limit]
            db_res = [JobResult.from_dict(r) for r in response.data]
            combined = db_res + [r for r in self._shared_memory_results if not any(d.id == r.id for d in db_res)]
            return combined[offset : offset + limit]
        except Exception as exc:
            logger.warning(f"Failed to query all job_results from DB: {str(exc)}")
            return self._shared_memory_results[offset : offset + limit]

    def get_summary_by_job_id(self, job_id: UUID) -> Dict[str, Any]:
        """Calculate row processing summary metrics for a job."""
        results = self.get_results_by_job_id(job_id)
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        return {
            "total_rows": total,
            "successful_rows": success,
            "failed_rows": failed,
        }

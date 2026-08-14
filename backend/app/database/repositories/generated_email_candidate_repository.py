"""Repository layer for generated_email_candidates database operations with shared memory fallback."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import UUID
from supabase import Client

from app.config.logging import logger
from app.core.exceptions import DatabaseException, ValidationException
from app.database.supabase import get_supabase_client
from app.models.generated_email_candidate import GeneratedEmailCandidate


class GeneratedEmailCandidateRepository:
    """Data access repository for generated candidate email permutations."""

    TABLE_NAME = "generated_email_candidates"
    _shared_memory_candidates: List[GeneratedEmailCandidate] = []

    def __init__(self, client: Optional[Client] = None) -> None:
        """Initialize repository with injected Supabase database client and fallback in-memory store."""
        self._client = client

    def _get_client(self) -> Optional[Client]:
        """Retrieve configured client or fallback singleton."""
        if self._client is not None:
            return self._client
        try:
            return get_supabase_client()
        except Exception as exc:
            logger.warning(f"Could not initialize Supabase client for candidates: {str(exc)}")
            return None

    @property
    def client(self) -> Client:
        """Access database client instance or raise DatabaseException if unconfigured."""
        client = self._get_client()
        if client is None:
            raise DatabaseException("Supabase database client is not configured or uninitialized")
        return client

    def insert_candidate(self, candidate: GeneratedEmailCandidate) -> GeneratedEmailCandidate:
        """Insert a single candidate email record into database or memory fallback."""
        return self.bulk_insert_candidates([candidate])[0]

    def bulk_insert_candidates(
        self,
        candidates: List[GeneratedEmailCandidate],
    ) -> List[GeneratedEmailCandidate]:
        """Bulk insert candidate records into database or fallback in-memory store."""
        if not candidates:
            return []

        now = datetime.now(timezone.utc)
        for c in candidates:
            if not c.created_at:
                c.created_at = now

        self._shared_memory_candidates.extend(candidates)

        client = self._get_client()
        if client is None:
            return candidates

        payloads = []
        for c in candidates:
            d = c.to_dict()
            if "id" in d and not d["id"]:
                del d["id"]
            payloads.append(d)

        try:
            response = client.table(self.TABLE_NAME).insert(payloads).execute()
            if not response.data or len(response.data) == 0:
                return candidates

            inserted = [GeneratedEmailCandidate.from_dict(item) for item in response.data]
            return inserted
        except Exception as exc:
            logger.warning(f"Candidates DB bulk insert warning ({str(exc)}). Saved in resilient memory store.")
            return candidates

    def get_candidates_by_job_id(self, job_id: UUID) -> List[GeneratedEmailCandidate]:
        """Retrieve all generated candidates for a specific job UUID, ordered by row_number, rank, and confidence_score."""
        if not job_id:
            raise ValidationException("Job ID must be provided")

        client = self._get_client()
        mem_candidates = [c for c in self._shared_memory_candidates if c.job_id == job_id]

        def sort_key(c: GeneratedEmailCandidate):
            rank_val = c.rank if c.rank is not None else 999
            return (c.row_number, rank_val, -c.confidence_score)

        if client is None:
            return sorted(mem_candidates, key=sort_key)

        try:
            response = (
                client.table(self.TABLE_NAME)
                .select("*")
                .eq("job_id", str(job_id))
                .order("row_number", desc=False)
                .order("confidence_score", desc=True)
                .execute()
            )
            if not response.data:
                return sorted(mem_candidates, key=sort_key)

            db_candidates = [GeneratedEmailCandidate.from_dict(record) for record in response.data]
            combined = db_candidates + [c for c in mem_candidates if not any(db_c.id == c.id for db_c in db_candidates)]
            return sorted(combined, key=sort_key)
        except Exception as exc:
            logger.warning(f"Failed to query generated_email_candidates for job '{job_id}': {str(exc)}. Returning memory store.")
            return sorted(mem_candidates, key=sort_key)

    def get_by_job_id(self, job_id: UUID) -> List[GeneratedEmailCandidate]:
        """Alias for get_candidates_by_job_id."""
        return self.get_candidates_by_job_id(job_id)

    def get_all(self, limit: int = 10000, offset: int = 0) -> List[GeneratedEmailCandidate]:
        """Retrieve all candidate records across all jobs."""
        client = self._get_client()
        if client is None:
            return self._shared_memory_candidates[offset : offset + limit]

        try:
            response = client.table(self.TABLE_NAME).select("*").range(offset, offset + limit - 1).execute()
            if not response.data:
                return self._shared_memory_candidates[offset : offset + limit]
            db_cand = [GeneratedEmailCandidate.from_dict(r) for r in response.data]
            combined = db_cand + [c for c in self._shared_memory_candidates if not any(d.id == c.id for d in db_cand)]
            return combined[offset : offset + limit]
        except Exception as exc:
            logger.warning(f"Failed to query all generated_email_candidates from DB: {str(exc)}")
            return self._shared_memory_candidates[offset : offset + limit]

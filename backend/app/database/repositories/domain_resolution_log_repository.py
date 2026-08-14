"""Repository layer for domain_resolution_logs audit database operations with fault-tolerant memory buffering."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
from supabase import Client

from app.config.logging import logger
from app.core.exceptions import (
    DatabaseException,
    EntityNotFoundException,
    ValidationException,
)
from app.database.supabase import get_supabase_client
from app.schemas.domain_resolution_log import (
    DomainLogCreate,
    DomainLogResponse,
)
from app.utils.normalization import normalize_company_name


class DomainResolutionLogRepository:
    """Data access repository for recording and querying domain resolution audit logs with resilient memory buffering."""

    TABLE_NAME = "domain_resolution_logs"
    _shared_memory_logs: List[DomainLogResponse] = []

    def __init__(self, client: Optional[Client] = None) -> None:
        """Initialize repository with injected Supabase database client or fallback singleton."""
        self._client = client

    def _get_client(self) -> Optional[Client]:
        """Retrieve injected client or fallback singleton."""
        if self._client is not None:
            return self._client
        try:
            return get_supabase_client()
        except Exception as exc:
            logger.warning(f"Could not initialize Supabase client for domain logs: {str(exc)}")
            return None

    @property
    def client(self) -> Client:
        """Access database client instance or raise exception if unconfigured."""
        client = self._get_client()
        if client is None:
            raise DatabaseException("Supabase database client is not configured or uninitialized")
        return client

    def insert_log(self, data: DomainLogCreate) -> DomainLogResponse:
        """Insert a new resolution audit log entry into database or resilient fallback buffer."""
        normalized = data.normalized_name
        if not normalized and data.company_name:
            normalized = normalize_company_name(data.company_name)

        now = datetime.now(timezone.utc)
        mem_log = DomainLogResponse(
            id=uuid4(),
            company_name=data.company_name,
            normalized_name=normalized,
            resolved_domain=data.resolved_domain,
            provider=data.provider,
            cached=data.cached,
            response_time_ms=data.response_time_ms,
            status=data.status,
            error_message=data.error_message,
            created_at=now,
        )
        self._shared_memory_logs.append(mem_log)

        client = self._get_client()
        if client is None:
            return mem_log

        payload = {
            "company_name": data.company_name,
            "normalized_name": normalized,
            "resolved_domain": data.resolved_domain,
            "provider": data.provider,
            "cached": data.cached,
            "response_time_ms": data.response_time_ms,
            "status": data.status,
            "error_message": data.error_message,
        }

        try:
            response = client.table(self.TABLE_NAME).insert(payload).execute()
            if response.data and len(response.data) > 0:
                return DomainLogResponse.model_validate(response.data[0])
            return mem_log
        except Exception as exc:
            logger.warning(f"Audit log DB insert warning ({str(exc)}). Log entry saved in resilient memory buffer.")
            return mem_log

    def get_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        company_name_filter: Optional[str] = None,
    ) -> List[DomainLogResponse]:
        """Retrieve audit log entries with optional status/company filtering and pagination."""
        if limit <= 0 or limit > 500:
            raise ValidationException("Limit must be between 1 and 500")
        if offset < 0:
            raise ValidationException("Offset cannot be negative")

        mem_filtered = list(self._shared_memory_logs)
        if status_filter:
            mem_filtered = [l for l in mem_filtered if l.status == status_filter]
        if company_name_filter:
            cn_low = company_name_filter.lower()
            mem_filtered = [l for l in mem_filtered if cn_low in l.company_name.lower()]

        client = self._get_client()
        if client is None:
            return mem_filtered[offset : offset + limit]

        try:
            query = client.table(self.TABLE_NAME).select("*")

            if status_filter:
                query = query.eq("status", status_filter)
            if company_name_filter:
                query = query.ilike("company_name", f"%{company_name_filter}%")

            query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
            response = query.execute()

            if not response.data:
                return mem_filtered[offset : offset + limit]

            db_logs = [DomainLogResponse.model_validate(record) for record in response.data]
            combined = db_logs + [l for l in mem_filtered if not any(d.id == l.id for d in db_logs)]
            return combined[offset : offset + limit]
        except Exception as exc:
            logger.warning(f"Failed to query resolution logs from DB: {str(exc)}. Returning memory store.")
            return mem_filtered[offset : offset + limit]

    def get_by_id(self, log_id: UUID) -> Optional[DomainLogResponse]:
        """Retrieve resolution log entry by primary key UUID."""
        if not log_id:
            raise ValidationException("Log ID must be provided")

        for l in self._shared_memory_logs:
            if l.id == log_id:
                return l

        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.table(self.TABLE_NAME).select("*").eq("id", str(log_id)).execute()

            if not response.data or len(response.data) == 0:
                return None

            return DomainLogResponse.model_validate(response.data[0])
        except Exception as exc:
            logger.warning(f"Failed to query resolution log by ID '{log_id}': {str(exc)}")
            return None

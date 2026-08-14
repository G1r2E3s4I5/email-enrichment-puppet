"""Repository layer for domain resolution analytics and quality metrics database queries."""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from supabase import Client

from app.config.logging import logger
from app.core.exceptions import DatabaseException
from app.database.supabase import get_supabase_client


class DomainAnalyticsRepository:
    """Data access repository executing optimized database queries for domain analytics and quality reporting."""

    def __init__(self, client: Optional[Client] = None) -> None:
        """Initialize repository with injected Supabase database client or fallback singleton."""
        self._client = client

    @property
    def client(self) -> Client:
        """Access database client instance or raise exception if unconfigured."""
        if self._client is not None:
            return self._client
        client = get_supabase_client()
        if client is None:
            raise DatabaseException("Supabase database client is not configured or uninitialized")
        return client

    def _get_window_start_time(self, time_window: str) -> Optional[datetime]:
        """Convert human-readable time window identifier to UTC datetime threshold."""
        now = datetime.now(timezone.utc)
        if time_window == "last_hour":
            return now - timedelta(hours=1)
        elif time_window == "last_24h":
            return now - timedelta(hours=24)
        elif time_window == "last_7d":
            return now - timedelta(days=7)
        elif time_window == "last_30d":
            return now - timedelta(days=30)
        elif time_window == "all_time":
            return None
        else:
            logger.warning(f"Unrecognized time window '{time_window}', defaulting to 'all_time'")
            return None

    def get_logs_in_window(self, time_window: str = "all_time") -> List[Dict[str, Any]]:
        """Retrieve all domain resolution audit logs created within specified time window."""
        start_time = self._get_window_start_time(time_window)
        try:
            query = self.client.table("domain_resolution_logs").select("*")
            if start_time:
                query = query.gte("created_at", start_time.isoformat())
            response = query.order("created_at", desc=True).execute()
            return response.data or []
        except Exception as exc:
            logger.error(f"Failed to fetch resolution logs for analytics (window={time_window}): {str(exc)}")
            return []

    def get_cached_domains_in_window(self, time_window: str = "all_time") -> List[Dict[str, Any]]:
        """Retrieve company domain cache records created within specified time window."""
        start_time = self._get_window_start_time(time_window)
        try:
            query = self.client.table("company_domains").select("*")
            if start_time:
                query = query.gte("created_at", start_time.isoformat())
            response = query.order("created_at", desc=True).execute()
            return response.data or []
        except Exception as exc:
            logger.error(f"Failed to fetch cached domains for analytics (window={time_window}): {str(exc)}")
            return []

    def get_total_cached_companies_count(self) -> int:
        """Query database count of active cached company domain entities."""
        try:
            response = self.client.table("company_domains").select("id", count="exact").execute()
            if response.count is not None:
                return response.count
            return len(response.data or [])
        except Exception as exc:
            logger.error(f"Failed to query total cached companies count: {str(exc)}")
            return 0

    def get_expired_cached_count(self, ttl_days: int = 30) -> int:
        """Query count of cached domain records created prior to TTL threshold."""
        threshold_iso = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
        try:
            response = (
                self.client.table("company_domains")
                .select("id", count="exact")
                .lt("created_at", threshold_iso)
                .execute()
            )
            if response.count is not None:
                return response.count
            return len(response.data or [])
        except Exception as exc:
            logger.error(f"Failed to query expired cached count: {str(exc)}")
            return 0

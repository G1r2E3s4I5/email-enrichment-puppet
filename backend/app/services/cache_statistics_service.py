"""Cache statistics service monitoring hit rates, misses, lookup latencies, and total cached entities."""

from typing import List, Optional
from datetime import datetime, timezone, timedelta
from supabase import Client

from app.config.logging import logger
from app.database.repositories.company_domain_repository import CompanyDomainRepository
from app.schemas.cache_statistics import CacheStatisticsResponse


class CacheStatisticsService:
    """Singleton service recording in-memory cache metrics and querying database cache totals."""

    def __init__(self, company_domain_repo: Optional[CompanyDomainRepository] = None) -> None:
        """Initialize statistics container and repository client."""
        self._company_domain_repo = company_domain_repo or CompanyDomainRepository()
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._lookup_times_ms: List[float] = []

    def record_hit(self, lookup_time_ms: float) -> None:
        """Record a successful cache hit event and track lookup duration."""
        self._cache_hits += 1
        self._lookup_times_ms.append(lookup_time_ms)
        if len(self._lookup_times_ms) > 1000:
            self._lookup_times_ms = self._lookup_times_ms[-1000:]
        logger.info(f"[Cache Hit]: Recorded hit in {lookup_time_ms:.2f}ms (Total hits: {self._cache_hits})")

    def record_miss(self, lookup_time_ms: float) -> None:
        """Record a cache miss event and track lookup duration."""
        self._cache_misses += 1
        self._lookup_times_ms.append(lookup_time_ms)
        if len(self._lookup_times_ms) > 1000:
            self._lookup_times_ms = self._lookup_times_ms[-1000:]
        logger.info(f"[Cache Miss]: Recorded miss in {lookup_time_ms:.2f}ms (Total misses: {self._cache_misses})")

    def record_refresh(self, company: Optional[str] = None) -> None:
        """Log cache refresh action for target company or all cached companies."""
        target_str = f"for '{company}'" if company else "for ALL cached companies"
        logger.info(f"[Cache Refresh]: Initiated cache refresh {target_str}")

    def get_statistics(self) -> CacheStatisticsResponse:
        """Compute and aggregate current cache telemetry metrics."""
        total_cached = 0
        expired_records = 0

        # Query database for actual cache row counts
        if self._company_domain_repo:
            try:
                client: Client = self._company_domain_repo.client
                # Total count
                resp = client.table("company_domains").select("id", count="exact").execute()
                total_cached = resp.count if resp.count is not None else len(resp.data or [])

                # Expired records count (> 30 days old)
                threshold_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                expired_resp = (
                    client.table("company_domains")
                    .select("id", count="exact")
                    .lt("created_at", threshold_iso)
                    .execute()
                )
                expired_records = expired_resp.count if expired_resp.count is not None else len(expired_resp.data or [])
            except Exception as exc:
                logger.warning(f"Database query failed when computing cache statistics: {str(exc)}")

        total_queries = self._cache_hits + self._cache_misses
        hit_rate = round((self._cache_hits / total_queries * 100.0), 2) if total_queries > 0 else 0.0

        avg_lookup_time = (
            round(sum(self._lookup_times_ms) / len(self._lookup_times_ms), 2)
            if self._lookup_times_ms
            else 0.0
        )

        return CacheStatisticsResponse(
            total_cached=total_cached,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            hit_rate=hit_rate,
            expired_records=expired_records,
            average_lookup_time=avg_lookup_time,
        )

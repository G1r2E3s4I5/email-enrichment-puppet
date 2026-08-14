"""Service layer aggregating domain resolution metrics, provider performance, cache analytics, and quality scoring."""

import statistics
from typing import List, Optional, Dict, Any

from app.config.logging import logger
from app.database.repositories.domain_analytics_repository import DomainAnalyticsRepository
from app.schemas.domain_analytics import (
    DomainAnalyticsOverviewResponse,
    DomainCacheAnalyticsResponse,
    DomainProviderAnalyticsResponse,
    DomainQualityAnalyticsResponse,
    ProviderStatisticItem,
    QualityDistribution,
)
from app.services.cache_statistics_service import CacheStatisticsService


class DomainAnalyticsService:
    """Production service layer computing domain analytics, quality distributions, and provider statistics DTOs."""

    def __init__(
        self,
        analytics_repo: Optional[DomainAnalyticsRepository] = None,
        cache_stats_service: Optional[CacheStatisticsService] = None,
    ) -> None:
        """Initialize analytics service with injected repository and cache monitor."""
        self._analytics_repo = analytics_repo or DomainAnalyticsRepository()
        self._cache_stats_service = cache_stats_service or CacheStatisticsService()

    def get_overview_analytics(self, time_window: str = "all_time") -> DomainAnalyticsOverviewResponse:
        """Compute high-level domain resolution metrics and performance summary."""
        logger.info(f"Analytics requested: GET /api/v1/domain/analytics/overview (Window: {time_window})")
        logs = self._analytics_repo.get_logs_in_window(time_window)

        total_resolutions = len(logs)
        successful_resolutions = sum(1 for log in logs if log.get("status") == "success")
        failed_resolutions = total_resolutions - successful_resolutions

        success_rate = round((successful_resolutions / total_resolutions * 100.0), 2) if total_resolutions > 0 else 0.0
        failure_rate = round((failed_resolutions / total_resolutions * 100.0), 2) if total_resolutions > 0 else 0.0

        cache_hits = sum(1 for log in logs if log.get("cached") is True)
        cache_hit_rate = round((cache_hits / total_resolutions * 100.0), 2) if total_resolutions > 0 else 0.0

        latencies = [log["response_time_ms"] for log in logs if log.get("response_time_ms") is not None]
        avg_response_time = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

        # Calculate average confidence from cached company domain records in window
        cached_records = self._analytics_repo.get_cached_domains_in_window(time_window)
        conf_scores = [r["confidence"] for r in cached_records if r.get("confidence") is not None]
        avg_confidence = round(sum(conf_scores) / len(conf_scores), 2) if conf_scores else 0.0

        logger.info(f"Overview generated: Total={total_resolutions}, SuccessRate={success_rate}%")
        return DomainAnalyticsOverviewResponse(
            time_window=time_window,
            total_resolutions=total_resolutions,
            successful_resolutions=successful_resolutions,
            failed_resolutions=failed_resolutions,
            success_rate=success_rate,
            failure_rate=failure_rate,
            cache_hit_rate=cache_hit_rate,
            average_response_time_ms=avg_response_time,
            average_confidence=avg_confidence,
        )

    def get_provider_analytics(self, time_window: str = "all_time") -> DomainProviderAnalyticsResponse:
        """Compute performance breakdown across all domain providers (Brandfetch, SerpAPI, Cache, etc.)."""
        logger.info(f"Analytics requested: GET /api/v1/domain/analytics/providers (Window: {time_window})")
        logs = self._analytics_repo.get_logs_in_window(time_window)

        provider_groups: Dict[str, List[Dict[str, Any]]] = {}
        for log in logs:
            prov = log.get("provider") or ("Cache" if log.get("cached") else "Unknown")
            if prov not in provider_groups:
                provider_groups[prov] = []
            provider_groups[prov].append(log)

        # Standard default provider list if no logs exist
        if not provider_groups:
            default_providers = ["Brandfetch", "SerpAPI", "Cache"]
            items = [
                ProviderStatisticItem(
                    provider=p,
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0,
                    average_response_time_ms=0.0,
                    fastest_response_ms=0.0,
                    slowest_response_ms=0.0,
                    average_confidence=0.0,
                )
                for p in default_providers
            ]
            logger.info(f"Provider analytics generated: {len(items)} default providers initialized")
            return DomainProviderAnalyticsResponse(time_window=time_window, providers=items)

        items: List[ProviderStatisticItem] = []
        for prov_name, group_logs in provider_groups.items():
            tot = len(group_logs)
            succ = sum(1 for l in group_logs if l.get("status") == "success")
            fail = tot - succ

            latencies = [l["response_time_ms"] for l in group_logs if l.get("response_time_ms") is not None]
            avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            fastest = round(min(latencies), 2) if latencies else 0.0
            slowest = round(max(latencies), 2) if latencies else 0.0

            # Default provider quality weight approximations
            prov_conf_map = {"Brandfetch": 90.0, "Cache": 85.0, "SerpAPI": 75.0, "Manual": 95.0}
            avg_conf = prov_conf_map.get(prov_name, 70.0) if succ > 0 else 0.0

            items.append(
                ProviderStatisticItem(
                    provider=prov_name,
                    total_requests=tot,
                    successful_requests=succ,
                    failed_requests=fail,
                    average_response_time_ms=avg_lat,
                    fastest_response_ms=fastest,
                    slowest_response_ms=slowest,
                    average_confidence=avg_conf,
                )
            )

        logger.info(f"Provider analytics generated: {len(items)} providers processed")
        return DomainProviderAnalyticsResponse(time_window=time_window, providers=items)

    def get_cache_analytics(self, time_window: str = "all_time") -> DomainCacheAnalyticsResponse:
        """Compute domain cache effectiveness, hit/miss percentages, and TTL expiration counts."""
        logger.info(f"Analytics requested: GET /api/v1/domain/analytics/cache (Window: {time_window})")
        logs = self._analytics_repo.get_logs_in_window(time_window)

        cache_hits = sum(1 for log in logs if log.get("cached") is True)
        cache_misses = sum(1 for log in logs if log.get("cached") is False)
        total_queries = cache_hits + cache_misses

        hit_rate = round((cache_hits / total_queries * 100.0), 2) if total_queries > 0 else 0.0
        miss_rate = round((cache_misses / total_queries * 100.0), 2) if total_queries > 0 else 0.0

        # Query active cached row counts and expired threshold records
        total_cached_companies = self._analytics_repo.get_total_cached_companies_count()
        expired_records_count = self._analytics_repo.get_expired_cached_count(ttl_days=30)
        cache_refresh_count = sum(1 for log in logs if "refresh" in str(log.get("provider", "")).lower() or "refresh" in str(log.get("error_message", "")).lower())

        logger.info(f"Cache analytics generated: HitRate={hit_rate}%")
        return DomainCacheAnalyticsResponse(
            time_window=time_window,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            cache_refresh_count=cache_refresh_count,
            expired_records_count=expired_records_count,
            total_cached_companies=total_cached_companies,
        )

    def get_quality_analytics(self, time_window: str = "all_time") -> DomainQualityAnalyticsResponse:
        """Compute quality score distribution, median confidence, and domain rejection metrics."""
        logger.info(f"Analytics requested: GET /api/v1/domain/analytics/quality (Window: {time_window})")
        cached_records = self._analytics_repo.get_cached_domains_in_window(time_window)
        logs = self._analytics_repo.get_logs_in_window(time_window)

        scores = [r["confidence"] for r in cached_records if r.get("confidence") is not None]

        avg_confidence = round(sum(scores) / len(scores), 2) if scores else 0.0
        median_confidence = round(float(statistics.median(scores)), 2) if scores else 0.0

        score_90_100 = sum(1 for s in scores if 90.0 <= s <= 100.0)
        score_80_89 = sum(1 for s in scores if 80.0 <= s < 90.0)
        score_70_79 = sum(1 for s in scores if 70.0 <= s < 80.0)
        below_70 = sum(1 for s in scores if s < 70.0)

        distribution = QualityDistribution(
            score_90_to_100=score_90_100,
            score_80_to_89=score_80_89,
            score_70_to_79=score_70_79,
            below_70=below_70,
        )

        suspicious_rejected = sum(
            1 for l in logs if l.get("status") != "success" and l.get("error_message") and any(kw in str(l.get("error_message")).lower() for kw in ["suspicious", "brand mismatch", "spoof"])
        )
        invalid_rejected = sum(
            1 for l in logs if l.get("status") != "success" and l.get("error_message") and any(kw in str(l.get("error_message")).lower() for kw in ["syntax", "tld", "empty", "short"])
        )
        duplicate_detected = sum(
            1 for l in logs if l.get("error_message") and "duplicate" in str(l.get("error_message")).lower()
        )

        logger.info(f"Quality report generated: AvgScore={avg_confidence}")
        return DomainQualityAnalyticsResponse(
            time_window=time_window,
            average_confidence=avg_confidence,
            median_confidence=median_confidence,
            confidence_distribution=distribution,
            duplicate_domains_count=duplicate_detected,
            suspicious_domains_rejected=suspicious_rejected,
            invalid_domains_rejected=invalid_rejected,
        )

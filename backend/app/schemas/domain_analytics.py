"""Pydantic schemas for domain resolution analytics, provider performance, cache metrics, and quality scoring."""

from typing import List, Optional
from pydantic import BaseModel, Field


class DomainAnalyticsOverviewResponse(BaseModel):
    """Overall domain resolution high-level metrics and performance summary."""

    time_window: str = Field(..., description="Time window for metrics (last_hour, last_24h, last_7d, last_30d, all_time)")
    total_resolutions: int = Field(..., description="Total domain resolution request count")
    successful_resolutions: int = Field(..., description="Total successful domain resolutions")
    failed_resolutions: int = Field(..., description="Total failed domain resolutions")
    success_rate: float = Field(..., description="Percentage of successful resolutions (0.0 to 100.0)")
    failure_rate: float = Field(..., description="Percentage of failed resolutions (0.0 to 100.0)")
    cache_hit_rate: float = Field(..., description="Percentage of resolutions served from cache (0.0 to 100.0)")
    average_response_time_ms: float = Field(..., description="Average resolution latency in milliseconds")
    average_confidence: float = Field(..., description="Average confidence quality score (0.0 to 100.0)")


class ProviderStatisticItem(BaseModel):
    """Telemetry and performance metrics for a specific domain resolution provider."""

    provider: str = Field(..., description="Provider name (e.g. Brandfetch, SerpAPI, Cache, Manual)")
    total_requests: int = Field(..., description="Total resolution requests sent to provider")
    successful_requests: int = Field(..., description="Successful resolutions by provider")
    failed_requests: int = Field(..., description="Failed resolution attempts by provider")
    average_response_time_ms: float = Field(..., description="Average provider latency in milliseconds")
    fastest_response_ms: float = Field(..., description="Fastest provider response time in milliseconds")
    slowest_response_ms: float = Field(..., description="Slowest provider response time in milliseconds")
    average_confidence: float = Field(..., description="Average confidence score returned by provider (0.0 to 100.0)")


class DomainProviderAnalyticsResponse(BaseModel):
    """Provider performance metrics breakdown across all domain providers."""

    time_window: str = Field(..., description="Time window for metrics")
    providers: List[ProviderStatisticItem] = Field(..., description="List of provider performance metrics")


class DomainCacheAnalyticsResponse(BaseModel):
    """Cache effectiveness, hit/miss metrics, and stored record analytics."""

    time_window: str = Field(..., description="Time window for metrics")
    cache_hits: int = Field(..., description="Total cache hit count")
    cache_misses: int = Field(..., description="Total cache miss count")
    hit_rate: float = Field(..., description="Cache hit rate percentage (0.0 to 100.0)")
    miss_rate: float = Field(..., description="Cache miss rate percentage (0.0 to 100.0)")
    cache_refresh_count: int = Field(..., description="Total cache refresh operations executed")
    expired_records_count: int = Field(..., description="Total cached records older than TTL threshold")
    total_cached_companies: int = Field(..., description="Total active company domains stored in database cache")


class QualityDistribution(BaseModel):
    """Confidence score distribution buckets."""

    score_90_to_100: int = Field(..., description="Count of resolutions with confidence score 90-100")
    score_80_to_89: int = Field(..., description="Count of resolutions with confidence score 80-89")
    score_70_to_79: int = Field(..., description="Count of resolutions with confidence score 70-79")
    below_70: int = Field(..., description="Count of resolutions with confidence score below 70")


class DomainQualityAnalyticsResponse(BaseModel):
    """Quality scoring analytics, confidence distribution, and domain rejection metrics."""

    time_window: str = Field(..., description="Time window for metrics")
    average_confidence: float = Field(..., description="Mean confidence score across resolutions (0.0 to 100.0)")
    median_confidence: float = Field(..., description="Median confidence score across resolutions (0.0 to 100.0)")
    confidence_distribution: QualityDistribution = Field(..., description="Bucket distribution of confidence scores")
    duplicate_domains_count: int = Field(..., description="Number of duplicate domain cache entries detected")
    suspicious_domains_rejected: int = Field(..., description="Count of suspicious domains rejected before caching")
    invalid_domains_rejected: int = Field(..., description="Count of syntactically invalid domains rejected before caching")

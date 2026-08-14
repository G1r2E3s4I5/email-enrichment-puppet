"""Pydantic schemas for domain cache intelligence statistics and cache refresh endpoints."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class CacheStatisticsResponse(BaseModel):
    """Analytics and metrics for company domain resolution cache behavior."""

    total_cached: int = Field(..., description="Total number of valid company domain entries in cache")
    cache_hits: int = Field(..., description="Cumulative number of cache hit operations")
    cache_misses: int = Field(..., description="Cumulative number of cache miss operations")
    hit_rate: float = Field(..., description="Percentage of queries served from cache (0.0 to 100.0)")
    expired_records: int = Field(..., description="Number of cached records that have passed TTL threshold")
    average_lookup_time: float = Field(..., description="Average cache lookup duration in milliseconds")


class CacheRefreshResponse(BaseModel):
    """Response payload for domain cache refresh operations."""

    success: bool = Field(True, description="Indicates whether the cache refresh executed successfully")
    company: Optional[str] = Field(None, description="Company name refreshed (for single-company refresh)")
    refreshed_count: int = Field(..., description="Total number of cached company entries refreshed")
    scanned_count: Optional[int] = Field(0, description="Total number of cache entries scanned")
    updated_records: Optional[List[str]] = Field(default_factory=list, description="List of updated domain names")
    execution_time_ms: Optional[float] = Field(0.0, description="Execution duration in milliseconds")
    message: str = Field("Cache refresh complete", description="Status summary of the refresh operation")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional contextual details")

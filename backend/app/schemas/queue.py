"""Pydantic validation schemas for Redis Job Queue and health monitoring."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class JobQueuePayload(BaseModel):
    """Payload stored in Redis for queued bulk enrichment jobs."""

    job_id: str = Field(..., description="Unique job identifier (UUID string)")
    stored_filename: str = Field(..., description="Unique filename stored on server disk")
    original_filename: str = Field(..., description="Original user-uploaded filename")
    upload_timestamp: str = Field(..., description="ISO 8601 upload timestamp string")
    row_count: int = Field(..., description="Total CSV data row count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Job metadata JSON (excluding CSV row contents)")

    model_config = ConfigDict(from_attributes=True)


class QueueJobResponse(BaseModel):
    """Response returned when a job is successfully pushed to the Redis queue."""

    success: bool = Field(default=True, description="Success status flag")
    job_id: str = Field(..., description="Queued job UUID string")
    status: str = Field(default="QUEUED", description="Updated job status")
    queue_position: int = Field(..., description="1-indexed position of job in Redis queue")

    model_config = ConfigDict(from_attributes=True)


class RedisHealthStatus(BaseModel):
    """Health check payload for Redis connection and performance metrics."""

    connected: bool = Field(..., description="Connection status flag")
    latency_ms: Optional[float] = Field(default=None, description="Ping round-trip latency in milliseconds")
    ping: bool = Field(default=False, description="Ping response status")
    memory_used_human: Optional[str] = Field(default=None, description="Human-readable memory usage string")
    error: Optional[str] = Field(default=None, description="Error message if Redis is unavailable")

    model_config = ConfigDict(from_attributes=True)


class QueueStatusResponse(BaseModel):
    """Response payload for GET /api/v1/queue/status detailing queue metrics and health."""

    redis: RedisHealthStatus = Field(..., description="Redis health and connection status")
    queue_size: int = Field(..., description="Total number of jobs waiting in queue")
    waiting_jobs: List[JobQueuePayload] = Field(default_factory=list, description="List of waiting queued jobs")

    model_config = ConfigDict(from_attributes=True)

"""Pydantic validation schemas for Background Worker Engine telemetry and responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class WorkerStatusResponse(BaseModel):
    """Schema for worker status inspection returning real-time telemetry."""

    running: bool = Field(..., description="Flag indicating if background worker loop is active")
    current_job: Optional[str] = Field(default=None, description="UUID string of currently active job being processed")
    processed_jobs: int = Field(default=0, description="Total number of jobs completed by worker")
    queue_size: int = Field(default=0, description="Current pending Redis queue size")
    uptime: str = Field(default="0s", description="Human-readable worker uptime string")
    last_activity: Optional[str] = Field(default=None, description="ISO timestamp of last worker activity")

    model_config = ConfigDict(from_attributes=True)


class WorkerStartResponse(BaseModel):
    """Response returned upon launching background worker loop."""

    success: bool = Field(default=True, description="Success status flag")
    message: str = Field(..., description="Action confirmation message")
    status: WorkerStatusResponse = Field(..., description="Current worker status snapshot")

    model_config = ConfigDict(from_attributes=True)


class WorkerStopResponse(BaseModel):
    """Response returned upon signalling worker loop graceful shutdown."""

    success: bool = Field(default=True, description="Success status flag")
    message: str = Field(..., description="Action confirmation message")
    status: WorkerStatusResponse = Field(..., description="Current worker status snapshot")

    model_config = ConfigDict(from_attributes=True)


class JobResultResponse(BaseModel):
    """Schema for individual row resolution results."""

    id: Optional[UUID] = Field(default=None, description="Row result primary key UUID")
    job_id: UUID = Field(..., description="Associated job UUID")
    row_number: int = Field(..., description="1-indexed CSV data row number")
    company: str = Field(..., description="Original company name from CSV")
    resolved_domain: Optional[str] = Field(default=None, description="Resolved domain string")
    provider: Optional[str] = Field(default=None, description="Domain resolution provider name")
    cached: bool = Field(default=False, description="Flag indicating if result was retrieved from cache")
    success: bool = Field(default=False, description="Flag indicating if domain resolution succeeded")
    error_message: Optional[str] = Field(default=None, description="Error message if row resolution failed")
    processed_at: Optional[datetime] = Field(default=None, description="Timestamp when row was processed")

    model_config = ConfigDict(from_attributes=True)

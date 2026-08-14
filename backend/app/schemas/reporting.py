"""Pydantic schemas for Phase 5 Production Platform, Reporting, Exports, and Analytics."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field


class JobSummary(BaseModel):
    """Job summary schema for dashboard listings."""

    job_id: UUID
    original_filename: str = Field(default="")
    status: str = Field(default="UPLOADED")
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    row_count: int = Field(default=0)
    processed_rows: int = Field(default=0)
    successful_rows: int = Field(default=0)
    failed_rows: int = Field(default=0)
    duration_sec: Optional[float] = None
    progress_percentage: float = 0.0
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    """Paginated list response schema for jobs dashboard."""

    total_count: int = Field(default=0)
    limit: int = Field(default=50)
    offset: int = Field(default=0)
    jobs: List[JobSummary] = Field(default_factory=list)


class JobStatisticsResponse(BaseModel):
    """Granular statistics for a single processing job."""

    job_id: UUID
    status: str = Field(default="COMPLETED")
    original_filename: str = Field(default="")
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_sec: Optional[float] = None
    row_count: int = Field(default=0)
    processed_rows: int = Field(default=0)
    successful_rows: int = Field(default=0)
    failed_rows: int = Field(default=0)
    companies_resolved: int = Field(default=0)
    cache_hit_count: int = Field(default=0)
    cache_hit_rate: float = Field(default=0.0)
    verification_success_rate: float = Field(default=0.0)
    average_confidence: float = Field(default=0.0)
    average_ranking_score: float = Field(default=0.0)
    total_candidates_generated: int = Field(default=0)
    provider_usage: Dict[str, int] = Field(default_factory=dict)


class JobErrorReportResponse(BaseModel):
    """Granular diagnostic error report for a job."""

    job_id: UUID
    status: str = Field(default="FAILED")
    error_message: Optional[str] = None
    failed_rows: List[Dict[str, Any]] = Field(default_factory=list)
    failed_companies: List[str] = Field(default_factory=list)
    verification_failures: List[Dict[str, Any]] = Field(default_factory=list)
    provider_failures: List[Dict[str, Any]] = Field(default_factory=list)
    retry_statistics: Dict[str, Any] = Field(default_factory=dict)


class PlatformAnalyticsResponse(BaseModel):
    """Platform-wide aggregated operational analytics."""

    total_jobs: int = Field(default=0)
    jobs_by_status: Dict[str, int] = Field(default_factory=dict)
    total_companies_processed: int = Field(default=0)
    average_job_duration_sec: float = Field(default=0.0)
    total_emails_generated: int = Field(default=0)
    verification_success_rate: float = Field(default=0.0)
    cache_hit_rate: float = Field(default=0.0)
    average_confidence_score: float = Field(default=0.0)
    provider_usage_breakdown: Dict[str, int] = Field(default_factory=dict)
    top_resolved_domains: List[Dict[str, Any]] = Field(default_factory=list)
    most_common_email_patterns: List[Dict[str, Any]] = Field(default_factory=list)


class SystemMetrics(BaseModel):
    """System CPU and memory usage statistics."""

    cpu_percent: float = Field(default=0.0)
    memory_mb: float = Field(default=0.0)
    memory_percent: float = Field(default=0.0)


class WorkerTelemetryResponse(BaseModel):
    """Live worker operational health and monitoring telemetry."""

    worker_status: str = Field(default="healthy")
    current_job_id: Optional[str] = None
    queue_length: int = Field(default=0)
    jobs_completed_total: int = Field(default=0)
    throughput_rows_per_sec: float = Field(default=0.0)
    throughput_emails_per_sec: float = Field(default=0.0)
    system_metrics: SystemMetrics = Field(default_factory=SystemMetrics)

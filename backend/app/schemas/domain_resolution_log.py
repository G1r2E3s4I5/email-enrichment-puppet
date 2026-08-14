"""Pydantic schemas for domain_resolution_logs table audit records."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DomainLogCreate(BaseModel):
    """Schema for recording a new domain resolution audit log entry."""

    company_name: Optional[str] = Field(default=None, description="Original queried company name")
    normalized_name: Optional[str] = Field(default=None, description="Normalized company name")
    resolved_domain: Optional[str] = Field(default=None, description="Domain found during resolution")
    provider: Optional[str] = Field(default=None, description="Provider that resolved the request")
    cached: bool = Field(default=False, description="Flag indicating if domain was served from cache")
    response_time_ms: Optional[int] = Field(default=None, ge=0, description="Response latency in milliseconds")
    status: str = Field(..., description="Resolution outcome status (e.g., success, not_found, error)")
    error_message: Optional[str] = Field(default=None, description="Error message details if resolution failed")


class DomainLogResponse(DomainLogCreate):
    """Schema for returning domain resolution log entry details."""

    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

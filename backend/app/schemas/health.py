"""Health check and service info schemas."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ServiceStatusResponse(BaseModel):
    """Schema for root status endpoint GET /."""

    service: str = Field(default="Email Enrichment Tool", description="Service name")
    status: str = Field(default="running", description="Current operational status")


class HealthCheckResponse(BaseModel):
    """Schema for health endpoint GET /health."""

    status: str = Field(default="healthy", description="Application health status")
    database: Optional[Dict[str, Any]] = Field(default=None, description="Database connectivity breakdown")

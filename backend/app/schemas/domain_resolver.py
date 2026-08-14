"""Pydantic schemas for DomainResolverService response payload."""

from typing import Optional
from pydantic import BaseModel, Field


class ResolverDomainResult(BaseModel):
    """Standardized result schema returned by DomainResolverService."""

    success: bool = Field(..., description="Flag indicating if domain resolution succeeded")
    company: str = Field(..., description="Original company query string")
    domain: Optional[str] = Field(default=None, description="Resolved official company domain")
    provider: Optional[str] = Field(default=None, description="Source provider used (Cache, Brandfetch, SerpAPI, or None)")
    cached: bool = Field(default=False, description="Flag indicating if response was served from cache")
    confidence: float = Field(default=0.0, ge=0.0, le=100.0, description="Domain resolution confidence score (0.0 to 100.0)")
    error: Optional[str] = Field(default=None, description="Error message details if resolution failed")

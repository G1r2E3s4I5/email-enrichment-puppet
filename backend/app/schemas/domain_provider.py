"""Pydantic schemas for standardized domain resolution provider responses."""

from typing import Optional
from pydantic import BaseModel, Field


class DomainResolutionResult(BaseModel):
    """Standardized response contract for all domain resolution providers."""

    success: bool = Field(..., description="Flag indicating if domain resolution succeeded")
    company: str = Field(..., description="Original or normalized company query string")
    domain: Optional[str] = Field(default=None, description="Resolved web domain name (e.g., stripe.com)")
    provider: str = Field(..., description="Name of the domain resolution provider used")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Provider confidence score (0.0 to 1.0)")
    error: Optional[str] = Field(default=None, description="Error message details if resolution failed")

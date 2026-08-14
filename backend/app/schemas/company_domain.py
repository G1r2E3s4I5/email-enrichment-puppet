"""Pydantic schemas for company_domains table data validation and serialization."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CompanyDomainBase(BaseModel):
    """Base schema for CompanyDomain attributes."""

    company_name: str = Field(default="", description="Original company name")
    domain: str = Field(default="", description="Resolved web domain")
    provider: str = Field(default="", description="Source provider used for resolution")
    confidence: float = Field(default=100.0, ge=0.0, le=100.0, description="Resolution confidence score (0.0 to 100.0)")
    preferred_pattern: Optional[str] = Field(default=None, description="Learned top email pattern for company")
    pattern_confidence: float = Field(default=0.0, description="Confidence score for learned pattern")
    pattern_last_verified_at: Optional[datetime] = Field(default=None, description="Timestamp when pattern was last verified")


class CompanyDomainCreate(CompanyDomainBase):
    """Schema for inserting a new company domain cache record."""

    normalized_name: Optional[str] = Field(
        default=None,
        description="Normalized company name (will be generated automatically if omitted)",
    )


class CompanyDomainUpdate(BaseModel):
    """Schema for updating an existing company domain cache record."""

    company_name: Optional[str] = Field(default=None, min_length=1)
    normalized_name: Optional[str] = Field(default=None, min_length=1)
    domain: Optional[str] = Field(default=None, min_length=1)
    provider: Optional[str] = Field(default=None, min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    preferred_pattern: Optional[str] = Field(default=None)
    pattern_confidence: Optional[float] = Field(default=None)
    pattern_last_verified_at: Optional[datetime] = Field(default=None)


class CompanyDomainResponse(CompanyDomainBase):
    """Schema for returning company domain cache record details."""

    id: UUID
    normalized_name: str = Field(default="")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

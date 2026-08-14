"""Pydantic validation schemas for domain resolution production API routes."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.domain_resolver import ResolverDomainResult


class DomainResolveRequest(BaseModel):
    """Payload schema for single company domain resolution endpoint."""

    company: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Company name to resolve domain for",
        json_schema_extra={"example": "Stripe"},
    )


class BatchDomainResolveRequest(BaseModel):
    """Payload schema for batch-preview domain resolution endpoint."""

    companies: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of company names to resolve (minimum 1, maximum 10)",
        json_schema_extra={"example": ["Stripe", "OpenAI", "Netflix"]},
    )


class BatchDomainResolutionResponse(BaseModel):
    """Summary response payload schema for batch-preview domain resolution."""

    total: int = Field(..., description="Total number of companies requested")
    successful: int = Field(..., description="Number of successfully resolved domains")
    failed: int = Field(..., description="Number of failed resolutions")
    results: List[ResolverDomainResult] = Field(..., description="List of domain resolution results")

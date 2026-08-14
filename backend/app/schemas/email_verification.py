"""Pydantic schemas for email verification requests, standardized responses, and provider health status."""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class EmailVerificationRequest(BaseModel):
    """Payload schema for single email verification requests."""

    email: str = Field(..., min_length=3, description="Candidate email address to verify")


class EmailVerificationResponse(BaseModel):
    """Standardized result schema returned by email verification providers."""

    email: str = Field(..., description="Target email address verified")
    status: str = Field(..., description="Verification status: valid, invalid, catch_all, or unknown")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Verification confidence quality score (0.0 to 100.0)")
    is_disposable: bool = Field(default=False, description="Indicates if the domain is a temporary/disposable email service")
    is_role_account: bool = Field(default=False, description="Indicates if the email is a role account (e.g. admin@, info@)")
    is_catch_all: bool = Field(default=False, description="Indicates if the target domain is configured as a catch-all server")
    mx_checked: bool = Field(default=True, description="Indicates if MX record lookup was performed")
    smtp_checked: bool = Field(default=False, description="Indicates if SMTP handshake verification was performed")
    provider: str = Field(..., description="Name of the verification provider used")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional provider-specific metadata")


class VerificationProviderListResponse(BaseModel):
    """Payload returning active and supported email verification provider keys."""

    active_provider: str = Field(..., description="Key of the currently configured active provider")
    supported_providers: List[str] = Field(..., description="List of all supported provider keys")


class VerificationProviderHealthResponse(BaseModel):
    """Payload returning health and connectivity status of the verification provider."""

    provider: str = Field(..., description="Provider name")
    status: str = Field(..., description="Health status (healthy, degraded, unreachable)")
    connected: bool = Field(..., description="Flag indicating active connection")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional diagnostic details")


class EmailVerificationProviderArchitectureResponse(BaseModel):
    """Payload schema for GET /api/v1/email-verification/providers."""

    active_provider: str = Field(..., description="Active provider slug name")
    available_providers: List[str] = Field(..., description="Array of all available provider names")
    provider_status: Dict[str, Any] = Field(..., description="Active provider health status dictionary")

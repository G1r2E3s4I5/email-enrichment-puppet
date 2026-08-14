"""Standardized API response contracts."""

from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standardized top-level API response envelope."""

    success: bool = Field(default=True, description="Operation success flag")
    message: str = Field(default="Operation completed successfully", description="Summary status message")
    data: Optional[T] = Field(default=None, description="Response payload")
    error: Optional[Any] = Field(default=None, description="Detailed error information if failed")


class ErrorDetail(BaseModel):
    """Structured error payload details."""

    code: str = Field(..., description="Error code identifier")
    message: str = Field(..., description="Human readable error message")
    details: Optional[Any] = Field(default=None, description="Supplementary error contextual details")

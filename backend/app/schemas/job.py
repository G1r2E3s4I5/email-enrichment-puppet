"""Pydantic validation schemas for CSV uploads and job tracking."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CSVValidationResult(BaseModel):
    """Result payload from CSV validation service."""

    is_valid: bool = Field(..., description="Validation flag")
    original_filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    headers: List[str] = Field(default_factory=list, description="Extracted CSV header columns")
    total_rows: int = Field(default=0, description="Total data row count")
    preview: List[Dict[str, Any]] = Field(default_factory=list, description="Preview of first 10 rows")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")


class JobUploadResponse(BaseModel):
    """Response model returned upon successful CSV upload & validation."""

    job_id: UUID = Field(..., description="Unique job identifier")
    status: str = Field(default="VALIDATED", description="Initial job status (UPLOADED/VALIDATED)")
    original_filename: str = Field(..., description="Original uploaded filename")
    stored_filename: str = Field(..., description="Stored unique filename in uploads directory")
    file_size: int = Field(..., description="File size in bytes")
    rows: int = Field(..., description="Total row count")
    headers: List[str] = Field(..., description="Extracted CSV header columns")
    preview: List[Dict[str, Any]] = Field(..., description="First 10 rows preview")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")

    model_config = ConfigDict(from_attributes=True)


class JobDetailResponse(BaseModel):
    """Detailed job status response model."""

    id: UUID = Field(..., description="Job UUID")
    status: str = Field(..., description="Current job status")
    original_filename: str = Field(..., description="Original uploaded filename")
    stored_filename: str = Field(..., description="Stored unique filename")
    file_size: int = Field(default=0, description="File size in bytes")
    total_rows: int = Field(default=0, description="Total row count")
    processed_rows: int = Field(default=0, description="Processed row count")
    successful_rows: int = Field(default=0, description="Successfully enriched row count")
    failed_rows: int = Field(default=0, description="Failed row count")
    progress_percentage: float = Field(default=0.0, description="Processing progress percentage (0-100)")

    created_at: Optional[datetime] = Field(default=None, description="Job creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    queued_at: Optional[datetime] = Field(default=None, description="Job queuing timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job processing start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")

    error_message: Optional[str] = Field(default=None, description="Job failure error message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Job metadata JSON")

    model_config = ConfigDict(from_attributes=True)

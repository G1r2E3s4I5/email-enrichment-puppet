"""Pydantic schemas for email pattern metadata and candidate REST API responses."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, model_serializer


class EmailPatternSchema(BaseModel):
    """Schema representing supported corporate email pattern metadata."""

    pattern_name: str = Field(..., description="Unique slug name of pattern (e.g. 'first.last')")
    template: str = Field(..., description="Format template representation (e.g. '{first}.{last}')")
    description: str = Field(..., description="Human-readable description of pattern structure")
    base_confidence: float = Field(..., ge=0.0, le=1.0, description="Baseline enterprise popularity score (0.0 to 1.0)")
    example: str = Field(..., description="Example output candidate email string")


class EmailPatternListResponse(BaseModel):
    """API response model listing all supported email patterns."""

    total_patterns: int = Field(..., description="Total count of supported email patterns")
    patterns: List[EmailPatternSchema] = Field(..., description="Array of supported email patterns")


class GeneratedCandidateResponse(BaseModel):
    """Schema representing a single generated and verified candidate email address."""

    id: Optional[UUID] = Field(None, description="Candidate record unique UUID")
    job_id: UUID = Field(..., description="Parent job UUID")
    row_number: int = Field(..., description="Original CSV data row index")
    candidate_email: str = Field(..., description="Generated candidate email address")
    pattern_name: str = Field(..., description="Pattern identifier used for generation")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Baseline pattern confidence score")
    pattern_score: Optional[float] = Field(None, description="Raw pattern baseline score")
    final_score: Optional[float] = Field(None, description="Recalculated quality score combining verification and penalties")
    verification_status: Optional[str] = Field(None, description="Deliverability status (VALID, INVALID, CATCH_ALL, UNKNOWN)")
    verification_confidence: Optional[float] = Field(None, description="Verification confidence quality score (0.0 to 100.0)")
    verification_provider: Optional[str] = Field(None, description="Verification provider used")
    is_disposable: bool = Field(default=False, description="Disposable domain flag")
    is_role_account: bool = Field(default=False, description="Role account flag")
    is_catch_all: bool = Field(default=False, description="Catch-all domain flag")
    rank: Optional[int] = Field(None, description="Quality rank position (1-based integer, 1 = best candidate)")
    verified_at: Optional[datetime] = Field(None, description="Verification timestamp")
    created_at: Optional[datetime] = Field(None, description="Generation timestamp")

    @model_serializer(mode="wrap")
    def serialize_candidate(self, handler) -> Dict[str, Any]:
        """Custom serializer providing standardized payload formatting."""
        data = handler(self)
        pat_score = self.pattern_score if self.pattern_score is not None else float(self.confidence_score)
        fin_score = self.final_score if self.final_score is not None else float(self.confidence_score)

        data["email"] = self.candidate_email
        data["pattern"] = self.pattern_name
        data["pattern_score"] = round(pat_score, 4)
        data["final_score"] = round(fin_score, 4)
        return data


class JobEmailCandidatesResponse(BaseModel):
    """API response model for GET /api/v1/jobs/{job_id}/email-candidates."""

    job_id: UUID = Field(..., description="Job UUID")
    total_candidates: int = Field(..., description="Total generated candidates count across all rows")
    candidates: List[GeneratedCandidateResponse] = Field(..., description="List of generated candidates sorted by rank")

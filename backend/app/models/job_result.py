"""Domain model representation for job_results table entity."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass
class JobResult:
    """JobResult domain entity model representing a processed row in a bulk job."""

    id: Optional[UUID]
    job_id: UUID
    row_number: int
    company: str
    resolved_domain: Optional[str] = None
    provider: Optional[str] = None
    cached: bool = False
    success: bool = False
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to dictionary format for DB operations."""
        data: Dict[str, Any] = {
            "job_id": str(self.job_id),
            "row_number": self.row_number,
            "company": self.company,
            "resolved_domain": self.resolved_domain,
            "provider": self.provider,
            "cached": self.cached,
            "success": self.success,
            "error_message": self.error_message,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.processed_at:
            data["processed_at"] = self.processed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobResult":
        """Construct model instance from database dictionary payload handling nulls safely."""
        processed_at_val = data.get("processed_at")
        processed_dt: Optional[datetime] = None
        if processed_at_val:
            try:
                if isinstance(processed_at_val, datetime):
                    processed_dt = processed_at_val
                else:
                    clean_str = str(processed_at_val).replace("Z", "+00:00")
                    processed_dt = datetime.fromisoformat(clean_str)
            except Exception:
                processed_dt = datetime.now(timezone.utc)

        def _parse_int(val: Any, default: int = 0) -> int:
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        return cls(
            id=UUID(str(data["id"])) if data.get("id") else None,
            job_id=UUID(str(data["job_id"])) if data.get("job_id") else UUID("00000000-0000-0000-0000-000000000000"),
            row_number=_parse_int(data.get("row_number"), 0),
            company=str(data.get("company") or ""),
            resolved_domain=data.get("resolved_domain"),
            provider=data.get("provider"),
            cached=bool(data.get("cached", False)),
            success=bool(data.get("success", False)),
            error_message=data.get("error_message"),
            processed_at=processed_dt,
        )

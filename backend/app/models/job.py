"""Domain model representation for processing_jobs table entity."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID


@dataclass
class ProcessingJob:
    """ProcessingJob domain entity model."""

    id: Optional[UUID]
    status: str
    original_filename: str
    stored_filename: str
    file_size: int = 0
    total_rows: int = 0
    processed_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def row_count(self) -> int:
        """Alias property for total_rows."""
        return self.total_rows

    @property
    def duration_sec(self) -> Optional[float]:
        """Calculate processing duration in seconds if timestamps are present."""
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at).total_seconds(), 2)
        elif self.created_at and self.completed_at:
            return round((self.completed_at - self.created_at).total_seconds(), 2)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to dictionary format for DB operations."""
        data: Dict[str, Any] = {
            "status": self.status,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_size": self.file_size,
            "total_rows": self.total_rows,
            "processed_rows": self.processed_rows,
            "successful_rows": self.successful_rows,
            "failed_rows": self.failed_rows,
            "error_message": self.error_message,
            "metadata": self.metadata or {},
        }
        if self.id:
            data["id"] = str(self.id)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        if self.queued_at:
            data["queued_at"] = self.queued_at.isoformat()
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingJob":
        """Construct model instance from database dictionary payload handling nulls and optional fields safely."""
        def _parse_dt(val: Any) -> Optional[datetime]:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            try:
                clean_str = str(val).replace("Z", "+00:00")
                return datetime.fromisoformat(clean_str)
            except Exception:
                return None

        def _parse_int(val: Any, default: int = 0) -> int:
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        total_rows_val = _parse_int(data.get("total_rows") if data.get("total_rows") is not None else data.get("row_count"), 0)

        return cls(
            id=UUID(str(data["id"])) if data.get("id") else None,
            status=str(data.get("status") or "UPLOADED"),
            original_filename=str(data.get("original_filename") or ""),
            stored_filename=str(data.get("stored_filename") or ""),
            file_size=_parse_int(data.get("file_size"), 0),
            total_rows=total_rows_val,
            processed_rows=_parse_int(data.get("processed_rows"), 0),
            successful_rows=_parse_int(data.get("successful_rows"), 0),
            failed_rows=_parse_int(data.get("failed_rows"), 0),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
            queued_at=_parse_dt(data.get("queued_at")),
            started_at=_parse_dt(data.get("started_at")),
            completed_at=_parse_dt(data.get("completed_at")),
            error_message=data.get("error_message"),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        )

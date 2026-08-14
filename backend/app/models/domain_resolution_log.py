"""Domain model representation for domain_resolution_logs table audit entity."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


@dataclass
class DomainResolutionLog:
    """DomainResolutionLog domain entity model."""

    id: Optional[UUID]
    company_name: Optional[str]
    normalized_name: Optional[str]
    resolved_domain: Optional[str]
    provider: Optional[str]
    cached: bool = False
    response_time_ms: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to dictionary format for DB operations."""
        data: Dict[str, Any] = {
            "company_name": self.company_name,
            "normalized_name": self.normalized_name,
            "resolved_domain": self.resolved_domain,
            "provider": self.provider,
            "cached": self.cached,
            "response_time_ms": self.response_time_ms,
            "status": self.status,
            "error_message": self.error_message,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainResolutionLog":
        """Construct model instance from database dictionary payload."""
        return cls(
            id=UUID(data["id"]) if data.get("id") else None,
            company_name=data.get("company_name"),
            normalized_name=data.get("normalized_name"),
            resolved_domain=data.get("resolved_domain"),
            provider=data.get("provider"),
            cached=bool(data.get("cached", False)),
            response_time_ms=data.get("response_time_ms"),
            status=data.get("status", "unknown"),
            error_message=data.get("error_message"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
        )

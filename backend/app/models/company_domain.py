"""Domain model representation for company_domains table entity."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


@dataclass
class CompanyDomain:
    """CompanyDomain domain entity model."""

    id: Optional[UUID]
    company_name: str
    normalized_name: str
    domain: str
    provider: str
    confidence: float = 1.0
    preferred_pattern: Optional[str] = None
    pattern_confidence: float = 0.0
    pattern_last_verified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to dictionary format for DB operations."""
        data: Dict[str, Any] = {
            "company_name": self.company_name,
            "normalized_name": self.normalized_name,
            "domain": self.domain,
            "provider": self.provider,
            "confidence": self.confidence,
            "preferred_pattern": self.preferred_pattern,
            "pattern_confidence": self.pattern_confidence,
        }
        if self.id:
            data["id"] = str(self.id)
        if self.pattern_last_verified_at:
            data["pattern_last_verified_at"] = self.pattern_last_verified_at.isoformat()
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompanyDomain":
        """Construct model instance from database dictionary payload."""
        return cls(
            id=UUID(data["id"]) if data.get("id") else None,
            company_name=data["company_name"],
            normalized_name=data["normalized_name"],
            domain=data["domain"],
            provider=data["provider"],
            confidence=float(data.get("confidence", 1.0)),
            preferred_pattern=data.get("preferred_pattern"),
            pattern_confidence=float(data.get("pattern_confidence", 0.0)),
            pattern_last_verified_at=datetime.fromisoformat(data["pattern_last_verified_at"]) if data.get("pattern_last_verified_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

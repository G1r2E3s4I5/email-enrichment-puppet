"""Domain model representation for generated_email_candidates table entity."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from uuid import UUID


@dataclass
class GeneratedEmailCandidate:
    """Domain model entity representing a generated and verified candidate email address."""

    id: Optional[UUID]
    job_id: UUID
    row_number: int
    candidate_email: str
    pattern_name: str
    confidence_score: float
    created_at: Optional[datetime] = None
    verification_status: Optional[str] = None
    verification_confidence: Optional[float] = None
    verification_provider: Optional[str] = None
    verified_at: Optional[datetime] = None
    is_disposable: bool = False
    is_role_account: bool = False
    is_catch_all: bool = False
    mx_checked: bool = True
    smtp_checked: bool = True
    verification_error: Optional[str] = None
    pattern_score: Optional[float] = None
    final_score: Optional[float] = None
    rank: Optional[int] = None

    # Phase 6.x Detailed Verification Metadata Fields
    mx_exists: bool = False
    mx_records: Optional[Any] = None
    smtp_status: Optional[str] = None
    smtp_code: Optional[int] = None
    smtp_message: Optional[str] = None
    verification_method: Optional[str] = None
    verification_duration_ms: float = 0.0
    verification_completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert model attributes to dictionary format for DB operations."""
        fin_score = self.final_score if self.final_score is not None else float(self.confidence_score)

        mx_rec_str = json.dumps(self.mx_records) if isinstance(self.mx_records, (list, dict)) else self.mx_records

        data: Dict[str, Any] = {
            "job_id": str(self.job_id),
            "row_number": self.row_number,
            "candidate_email": self.candidate_email,
            "pattern_name": self.pattern_name,
            "confidence_score": float(fin_score),
            "verification_status": self.verification_status,
            "verification_confidence": float(self.verification_confidence) if self.verification_confidence is not None else None,
            "verification_provider": self.verification_provider,
            "is_disposable": bool(self.is_disposable),
            "is_role_account": bool(self.is_role_account),
            "is_catch_all": bool(self.is_catch_all),
            "mx_checked": bool(self.mx_checked),
            "smtp_checked": bool(self.smtp_checked),
            "verification_error": self.verification_error,
            "rank": int(self.rank) if self.rank is not None else None,
            "mx_exists": bool(self.mx_exists),
            "mx_records": mx_rec_str,
            "smtp_status": self.smtp_status,
            "smtp_code": int(self.smtp_code) if self.smtp_code is not None else None,
            "smtp_message": self.smtp_message,
            "verification_method": self.verification_method or self.verification_provider,
            "verification_duration_ms": float(self.verification_duration_ms or 0.0),
        }
        if self.id:
            data["id"] = str(self.id)
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.verified_at:
            data["verified_at"] = self.verified_at.isoformat()
        if self.verification_completed_at:
            data["verification_completed_at"] = self.verification_completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneratedEmailCandidate":
        """Construct model instance from database dictionary payload handling nulls safely."""
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

        def _parse_float(val: Any, default: float = 0.0) -> float:
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def _parse_int(val: Any, default: int = 0) -> int:
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        created_dt = _parse_dt(data.get("created_at"))
        verified_dt = _parse_dt(data.get("verified_at"))
        completed_dt = _parse_dt(data.get("verification_completed_at")) or verified_dt

        pat_score = _parse_float(data.get("pattern_score"), _parse_float(data.get("confidence_score"), 0.0))
        fin_score = _parse_float(data.get("final_score"), _parse_float(data.get("confidence_score"), 0.0))

        rank_val = _parse_int(data.get("rank"), 0) if data.get("rank") is not None else None

        raw_mx_rec = data.get("mx_records")
        if isinstance(raw_mx_rec, str) and raw_mx_rec.startswith("["):
            try:
                parsed_mx = json.loads(raw_mx_rec)
            except Exception:
                parsed_mx = raw_mx_rec
        else:
            parsed_mx = raw_mx_rec

        return cls(
            id=UUID(str(data["id"])) if data.get("id") else None,
            job_id=UUID(str(data["job_id"])) if data.get("job_id") else UUID("00000000-0000-0000-0000-000000000000"),
            row_number=_parse_int(data.get("row_number"), 0),
            candidate_email=str(data.get("candidate_email") or ""),
            pattern_name=str(data.get("pattern_name") or ""),
            confidence_score=fin_score,
            created_at=created_dt,
            verification_status=data.get("verification_status"),
            verification_confidence=_parse_float(data.get("verification_confidence")) if data.get("verification_confidence") is not None else None,
            verification_provider=data.get("verification_provider"),
            verified_at=verified_dt,
            is_disposable=bool(data.get("is_disposable", False)),
            is_role_account=bool(data.get("is_role_account", False)),
            is_catch_all=bool(data.get("is_catch_all", False)),
            mx_checked=bool(data.get("mx_checked", True)),
            smtp_checked=bool(data.get("smtp_checked", True)),
            verification_error=data.get("verification_error"),
            pattern_score=pat_score,
            final_score=fin_score,
            rank=rank_val,
            mx_exists=bool(data.get("mx_exists", False)),
            mx_records=parsed_mx,
            smtp_status=data.get("smtp_status"),
            smtp_code=_parse_int(data.get("smtp_code")) if data.get("smtp_code") is not None else None,
            smtp_message=data.get("smtp_message"),
            verification_method=data.get("verification_method") or data.get("verification_provider"),
            verification_duration_ms=_parse_float(data.get("verification_duration_ms"), 0.0),
            verification_completed_at=completed_dt,
        )

"""PatternRankService evaluating confidence scores and ranking email candidates."""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from app.utils.string_normalizer import NormalizedName


@dataclass
class RankedCandidate:
    """Dataclass representing a ranked email candidate with confidence score."""

    candidate_email: str
    pattern_name: str
    confidence_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Return dict representation."""
        return {
            "candidate_email": self.candidate_email,
            "pattern_name": self.pattern_name,
            "confidence_score": self.confidence_score,
        }


@dataclass
class VerifiedRankedCandidate:
    """Dataclass representing a candidate email with verification metadata and rank position."""

    candidate_email: str
    pattern_name: str
    pattern_score: float
    verification_status: str
    verification_confidence: float
    verification_provider: str
    is_disposable: bool
    is_role_account: bool
    is_catch_all: bool
    rank: int
    final_score: float
    mx_checked: bool = True
    mx_exists: bool = False
    smtp_checked: bool = False
    smtp_status: Optional[str] = None
    smtp_message: Optional[str] = None
    verification_error: Optional[str] = None
    verified_at_iso: Optional[str] = None

    @property
    def composite_score(self) -> float:
        """Alias for final_score."""
        return self.final_score


class PatternRankService:
    """Service ranking candidate emails by enterprise popularity, verification status, and quality penalties."""

    def rank_and_deduplicate_candidates(
        self,
        raw_candidates: List[Tuple[str, str, float]],
        normalized_name: NormalizedName,
    ) -> List[RankedCandidate]:
        """Deduplicate and rank candidate emails in descending order of confidence score."""
        adjusted_items: List[Tuple[str, str, float]] = []
        is_complete_name = bool(normalized_name.first_name and normalized_name.last_name)

        for email, pattern_name, base_conf in raw_candidates:
            score = base_conf

            if is_complete_name and ("first" in pattern_name and "last" in pattern_name):
                score = min(1.0, score * 1.0)
            elif not is_complete_name:
                score = round(score * 0.85, 4)

            score = round(score, 4)
            adjusted_items.append((email, pattern_name, score))

        best_candidates: Dict[str, Tuple[str, float]] = {}

        for email, pattern_name, score in adjusted_items:
            if email not in best_candidates:
                best_candidates[email] = (pattern_name, score)
            else:
                existing_pattern, existing_score = best_candidates[email]
                if score > existing_score:
                    best_candidates[email] = (pattern_name, score)

        ranked_list: List[RankedCandidate] = [
            RankedCandidate(
                candidate_email=email,
                pattern_name=pat,
                confidence_score=score,
            )
            for email, (pat, score) in best_candidates.items()
        ]

        ranked_list.sort(key=lambda c: (-c.confidence_score, c.candidate_email))
        return ranked_list

    def rank_verified_candidates(
        self,
        verified_candidates: List[Dict[str, Any]],
    ) -> List[VerifiedRankedCandidate]:
        """Recalculate composite quality final_score and 1-based rank position for verified candidates with email deduplication."""
        # 1. Deduplicate input candidates by candidate_email (keep best)
        unique_map: Dict[str, Dict[str, Any]] = {}
        for c in verified_candidates:
            email_key = c.get("candidate_email", "").strip().lower()
            if not email_key:
                continue
            if email_key not in unique_map:
                unique_map[email_key] = c
            else:
                # Prefer VALID over INVALID/UNKNOWN
                existing = unique_map[email_key]
                ex_stat = str(existing.get("verification_status", "")).upper()
                new_stat = str(c.get("verification_status", "")).upper()
                if new_stat == "VALID" and ex_stat != "VALID":
                    unique_map[email_key] = c

        scored_list: List[Tuple[float, Dict[str, Any]]] = []

        for candidate in unique_map.values():
            pat_score = float(candidate.get("pattern_score", candidate.get("confidence_score", 0.5)))
            ver_status = str(candidate.get("verification_status", "UNKNOWN")).upper()
            ver_conf = float(candidate.get("verification_confidence", 0.0)) / 100.0

            is_disp = bool(candidate.get("is_disposable", False))
            is_role = bool(candidate.get("is_role_account", False))
            is_catch = bool(candidate.get("is_catch_all", False))

            # Base calculation combining pattern score & verification confidence
            if ver_status == "VALID":
                final = (pat_score * 0.4) + (ver_conf * 0.6)
            elif ver_status == "CATCH_ALL":
                final = (pat_score * 0.5) + (ver_conf * 0.5)
            elif ver_status in ("INVALID", "INVALID_DOMAIN"):
                final = 0.05
            elif ver_status in ("RISKY", "UNKNOWN"):
                mx_ex = bool(candidate.get("mx_exists", True))
                if mx_ex and ver_conf > 0:
                    final = (pat_score * 0.5) + (ver_conf * 0.5)
                else:
                    final = pat_score * 0.5
            else:
                final = (pat_score * 0.5) + (ver_conf * 0.5) if ver_conf > 0 else pat_score * 0.5

            # Penalties
            if is_disp:
                final = max(0.0, final - 0.5)
            if is_role:
                final = max(0.0, final - 0.2)
            if is_catch and ver_status != "CATCH_ALL":
                final = max(0.0, final - 0.2)

            final = round(final, 4)
            scored_list.append((final, candidate))

        # Sort descending by final_score, then pattern_score, then email
        scored_list.sort(
            key=lambda x: (
                -x[0],
                -float(x[1].get("pattern_score", x[1].get("confidence_score", 0.0))),
                x[1].get("candidate_email", ""),
            )
        )

        ranked_results: List[VerifiedRankedCandidate] = []
        for idx, (final_sc, item) in enumerate(scored_list, start=1):
            mx_c = bool(item.get("mx_checked", True))
            mx_ex = bool(item.get("mx_exists", True if item.get("verification_status", "").upper() != "INVALID_DOMAIN" else False))
            smtp_c = bool(item.get("smtp_checked", False))

            ranked_results.append(
                VerifiedRankedCandidate(
                    candidate_email=item.get("candidate_email", ""),
                    pattern_name=item.get("pattern_name", ""),
                    pattern_score=float(item.get("pattern_score", item.get("confidence_score", 0.5))),
                    verification_status=str(item.get("verification_status", "UNKNOWN")).upper(),
                    verification_confidence=float(item.get("verification_confidence", 0.0)),
                    verification_provider=str(item.get("verification_provider", "Composite")),
                    is_disposable=bool(item.get("is_disposable", False)),
                    is_role_account=bool(item.get("is_role_account", False)),
                    is_catch_all=bool(item.get("is_catch_all", False)),
                    rank=idx,
                    final_score=final_sc,
                    mx_checked=mx_c,
                    mx_exists=mx_ex,
                    smtp_checked=smtp_c,
                    smtp_status=item.get("smtp_status"),
                    smtp_message=item.get("smtp_message"),
                    verification_error=item.get("verification_error"),
                    verified_at_iso=item.get("verified_at_iso"),
                )
            )

        return ranked_results

"""VerificationScoringService calculating composite email verification confidence scores combining pattern, MX, SMTP, catch-all, disposable, and role metrics."""

from typing import Dict, Any
from app.config.settings import settings


class VerificationScoringService:
    """Production scoring engine producing final composite confidence score (0.0 - 100.0)."""

    @staticmethod
    def calculate_composite_score(
        pattern_confidence: float = 0.0,
        mx_valid: bool = False,
        smtp_valid: bool = False,
        is_catch_all: bool = False,
        is_disposable: bool = False,
        is_role_account: bool = False,
        mx_bonus: float = None,
        smtp_bonus: float = None,
        role_penalty: float = None,
        disposable_penalty: float = None,
        catch_all_penalty: float = None,
    ) -> float:
        if not mx_valid:
            return 0.0

        mx_b = mx_bonus if mx_bonus is not None else getattr(settings, "MX_CONFIDENCE_BONUS", 20.0)
        smtp_b = smtp_bonus if smtp_bonus is not None else getattr(settings, "SMTP_CONFIDENCE_BONUS", 40.0)
        role_p = role_penalty if role_penalty is not None else getattr(settings, "ROLE_ACCOUNT_PENALTY", 10.0)
        disp_p = disposable_penalty if disposable_penalty is not None else getattr(settings, "DISPOSABLE_PENALTY", 30.0)
        catch_p = catch_all_penalty if catch_all_penalty is not None else getattr(settings, "CATCH_ALL_PENALTY", 15.0)

        # Normalize pattern confidence to 0-100 scale if passed as 0.0-1.0
        base_score = pattern_confidence * 100.0 if pattern_confidence <= 1.0 else pattern_confidence
        base_score = max(0.0, min(100.0, base_score))

        score = base_score * 0.40  # 40% base pattern weight
        score += mx_b

        if smtp_valid:
            score += smtp_b

        if is_catch_all:
            score -= catch_p

        if is_disposable:
            score -= disp_p

        if is_role_account:
            score -= role_p

        return round(max(0.0, min(100.0, score)), 2)

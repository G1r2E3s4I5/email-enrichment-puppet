"""Unit and integration tests verifying audit remediation fixes for domain resolution, similarity checks, typo correction, and SMTP status consistency."""

import pytest
from app.services.domain_validation_service import DomainValidationService
from app.services.domain_resolver_service import DomainResolverService
from app.utils.normalization import normalize_company_name
from app.providers.email_verification.composite_provider import CompositeVerificationProvider
from app.services.verification_scoring_service import VerificationScoringService


def test_typo_correction_normalize_company_name() -> None:
    """Test typo auto-correction in company normalization."""
    assert normalize_company_name("micrsoft") == "microsoft"
    assert normalize_company_name("amazn") == "amazon"
    assert normalize_company_name("gooogle") == "google"
    assert normalize_company_name("facbook") == "meta"
    assert normalize_company_name("convegeniusai") in ("convegenius ai", "convegenius.ai")


def test_domain_similarity_validation() -> None:
    """Test domain similarity scoring and mismatch rejection."""
    val_service = DomainValidationService()

    # 1. Unrelated domain should have low similarity (< 0.35)
    sim_mismatch = val_service.calculate_domain_similarity("Convegenius AI", "airbnb.com")
    assert sim_mismatch < 0.35

    suspicious, reason = val_service.is_suspicious_domain("Convegenius AI", "airbnb.com")
    assert suspicious is True
    assert "Brand mismatch" in reason or "Low brand domain similarity" in reason

    # 2. Matching domain should have high similarity (>= 0.80)
    sim_match = val_service.calculate_domain_similarity("Convegenius AI", "convegenius.ai")
    assert sim_match >= 0.80

    suspicious_valid, _ = val_service.is_suspicious_domain("Convegenius AI", "convegenius.ai")
    assert suspicious_valid is False


@pytest.mark.asyncio
async def test_domain_resolver_convegenius_and_typo_resolution() -> None:
    """Test resolving Convegenius AI avoids airbnb.com and micrsoft resolves to microsoft.com."""
    resolver = DomainResolverService()

    # Test micrsoft typo resolution
    res_micrsoft = await resolver.resolve_domain("micrsoft")
    assert res_micrsoft.success is True
    assert res_micrsoft.domain == "microsoft.com"

    # Test Convegenius AI resolution
    res_convegenius = await resolver.resolve_domain("Convegenius AI")
    assert res_convegenius.success is True
    assert res_convegenius.domain != "airbnb.com"
    assert "convegenius" in res_convegenius.domain


@pytest.mark.asyncio
async def test_composite_provider_smtp_status_consistency() -> None:
    """Test SMTP connection_refused with MX existing produces 'valid' status with reduced confidence (no SMTP bonus)."""
    provider = CompositeVerificationProvider()

    # Mock SMTP provider response with connection_refused
    async def mock_refused_smtp(email, **kwargs):
        return {
            "status": "unknown",
            "smtp_code": 0,
            "smtp_message": "Connection refused by peer",
            "smtp_status": "connection_refused",
            "is_catch_all": False,
        }

    provider._smtp_provider.verify = mock_refused_smtp

    # Verify candidate email with MX valid but SMTP connection refused
    res = await provider.verify("test@stripe.com")

    # MX exists → valid even when SMTP unreachable (port 25 blocked is very common)
    assert res["status"] == "valid"
    assert res["error"] is None
    # Confidence should be reduced (no SMTP bonus of 40) but still meaningful
    assert res["confidence"] > 0.0


def test_verification_scoring_dynamic_values() -> None:
    """Test composite verification confidence score produces dynamic scores for varied conditions."""
    score_valid = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.9,
        mx_valid=True,
        smtp_valid=True,
    )
    score_no_smtp = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.7,
        mx_valid=True,
        smtp_valid=False,
    )
    score_catch_all = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.7,
        mx_valid=True,
        smtp_valid=False,
        is_catch_all=True,
    )
    score_no_mx = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.9,
        mx_valid=False,
    )

    assert score_valid > score_no_smtp
    assert score_no_smtp > score_catch_all
    assert score_no_mx == 0.0

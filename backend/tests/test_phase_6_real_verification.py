"""Automated unit and integration test suite for Phase 6.x Real Email Verification (MX, SMTP, Composite, Role, Disposable, Catch-All)."""

import pytest
from unittest.mock import patch, MagicMock
from app.config.settings import settings
from app.providers.email_verification.base import EmailVerificationProvider
from app.providers.email_verification.mock_provider import MockProvider
from app.providers.email_verification.mx_provider import MxVerificationProvider
from app.providers.email_verification.smtp_provider import SmtpEmailVerificationProvider
from app.providers.email_verification.composite_provider import CompositeVerificationProvider
from app.providers.email_verification.provider_registry import ProviderRegistry
from app.providers.email_verification.provider_factory import ProviderFactory
from app.utils.disposable_email_detector import DisposableEmailDetector
from app.utils.role_account_detector import RoleAccountDetector
from app.services.verification_scoring_service import VerificationScoringService


@pytest.mark.asyncio
async def test_role_account_detector():
    """Verify role account detection for standard prefixes."""
    detector = RoleAccountDetector()
    assert detector.is_role_account("info@stripe.com") is True
    assert detector.is_role_account("support@shopify.com") is True
    assert detector.is_role_account("admin@company.com") is True
    assert detector.is_role_account("john.doe@stripe.com") is False


@pytest.mark.asyncio
async def test_disposable_email_detector():
    """Verify disposable email domain detection."""
    detector = DisposableEmailDetector()
    assert detector.is_disposable("john@mailinator.com") is True
    assert detector.is_disposable("temp@10minutemail.com") is True
    assert detector.is_disposable("guerrilla@guerrillamail.com") is True
    assert detector.is_disposable("john@stripe.com") is False


@pytest.mark.asyncio
async def test_mx_verification_provider_valid():
    """Verify MX provider with valid DNS MX records."""
    provider = MxVerificationProvider()
    with patch.object(provider, "_query_mx_dns", return_value=(["mail.stripe.com"], 12.5)):
        res = await provider.verify("john@stripe.com")
        assert res["status"] == "valid"
        assert res["mx_exists"] is True
        assert "mail.stripe.com" in res["mx_records"]
        assert res["provider"] == "MX"
        assert res["confidence"] > 0.0


@pytest.mark.asyncio
async def test_mx_verification_provider_invalid_domain():
    """Verify MX provider with missing MX records returns INVALID_DOMAIN."""
    provider = MxVerificationProvider()
    with patch.object(provider, "_query_mx_dns", return_value=([], 5.0)):
        res = await provider.verify("john@nonexistentdomainxyz123.com")
        assert res["status"] == "INVALID_DOMAIN"
        assert res["mx_exists"] is False
        assert res["confidence"] == 0.0


@pytest.mark.asyncio
async def test_smtp_verification_provider_mailbox_exists():
    """Verify SMTP provider when mailbox exists."""
    provider = SmtpEmailVerificationProvider()
    with patch.object(provider, "_resolve_mx_records", return_value=["mail.stripe.com"]):
        with patch.object(provider, "_probe_smtp_handshake", return_value={
            "smtp_code": 250,
            "smtp_message": "2.1.5 OK",
            "smtp_status": "mailbox_exists",
            "mailbox_exists": True,
            "is_catch_all": False,
        }):
            res = await provider.verify("john@stripe.com")
            assert res["status"] == "valid"
            assert res["smtp_code"] == 250
            assert res["smtp_status"] == "mailbox_exists"
            assert res["is_catch_all"] is False
            assert res["confidence"] > 50.0


@pytest.mark.asyncio
async def test_smtp_verification_provider_mailbox_missing():
    """Verify SMTP provider when mailbox is missing on target server."""
    provider = SmtpEmailVerificationProvider()
    with patch.object(provider, "_resolve_mx_records", return_value=["mail.stripe.com"]):
        with patch.object(provider, "_probe_smtp_handshake", return_value={
            "smtp_code": 550,
            "smtp_message": "5.1.1 User unknown",
            "smtp_status": "mailbox_not_found",
            "mailbox_exists": False,
            "is_catch_all": False,
        }):
            res = await provider.verify("unknownuser123@stripe.com")
            assert res["status"] == "invalid"
            assert res["smtp_code"] == 550
            assert res["smtp_status"] == "mailbox_not_found"
            assert res["confidence"] == 0.0


@pytest.mark.asyncio
async def test_smtp_verification_provider_timeout():
    """Verify SMTP provider timeout handling."""
    provider = SmtpEmailVerificationProvider()
    with patch.object(provider, "_resolve_mx_records", return_value=["mail.stripe.com"]):
        with patch.object(provider, "_probe_smtp_handshake", return_value={
            "smtp_code": 408,
            "smtp_message": "Timeout connecting",
            "smtp_status": "timeout",
            "mailbox_exists": False,
            "is_catch_all": False,
        }):
            res = await provider.verify("john@stripe.com")
            assert res["status"] == "valid"  # MX exists → valid even if SMTP unreachable
            assert res["smtp_code"] == 408
            assert res["smtp_status"] == "timeout"


@pytest.mark.asyncio
async def test_composite_verification_provider_catch_all():
    """Verify Composite provider catch-all domain detection and penalty."""
    provider = CompositeVerificationProvider()
    with patch.object(provider._mx_provider, "verify", return_value={
        "mx_exists": True,
        "mx_records": ["mail.stripe.com"],
    }):
        with patch.object(provider._smtp_provider, "verify", return_value={
            "status": "valid",
            "smtp_code": 250,
            "smtp_message": "2.1.5 OK",
            "smtp_status": "catch_all",
            "is_catch_all": True,
        }):
            res = await provider.verify("john@stripe.com")
            assert res["is_catch_all"] is True
            assert res["provider"] == "Composite"
            assert res["confidence"] < 90.0  # Catch-all penalty applied


@pytest.mark.asyncio
async def test_composite_verification_provider_disposable():
    """Verify Composite provider rejects disposable emails."""
    provider = CompositeVerificationProvider()
    res = await provider.verify("john@mailinator.com")
    assert res["status"] == "invalid"
    assert res["is_disposable"] is True
    assert res["confidence"] == 0.0


@pytest.mark.asyncio
async def test_verification_scoring_service_composite_weights():
    """Verify scoring logic applies pattern weight, MX bonus, SMTP bonus, and risk penalties."""
    score_full = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.9,
        mx_valid=True,
        smtp_valid=True,
        is_catch_all=False,
        is_disposable=False,
        is_role_account=False,
    )
    score_role = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.9,
        mx_valid=True,
        smtp_valid=True,
        is_catch_all=False,
        is_disposable=False,
        is_role_account=True,
    )
    assert score_full > score_role  # Role account penalty reflected


@pytest.mark.asyncio
async def test_provider_factory_and_registry_switching():
    """Verify provider switching via ProviderFactory for mock, mx, smtp, and composite."""
    f_mock = ProviderFactory("mock").get_provider()
    assert f_mock.get_provider_name() == "Mock"

    f_mx = ProviderFactory("mx").get_provider()
    assert f_mx.get_provider_name() == "MX"

    f_smtp = ProviderFactory("smtp").get_provider()
    assert f_smtp.get_provider_name() == "SMTP"

    f_composite = ProviderFactory("composite").get_provider()
    assert f_composite.get_provider_name() == "Composite"

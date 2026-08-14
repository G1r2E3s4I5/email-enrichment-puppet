"""Unit tests for DomainValidationService."""

import pytest
from app.services.domain_validation_service import DomainValidationService, DomainValidationResult


@pytest.fixture
def validation_service() -> DomainValidationService:
    return DomainValidationService()


def test_validate_domain_syntax(validation_service: DomainValidationService):
    assert validation_service.validate_domain_syntax("google.com") is True
    assert validation_service.validate_domain_syntax("sub.domain.co.uk") is True
    assert validation_service.validate_domain_syntax("invalid_domain") is False
    assert validation_service.validate_domain_syntax("http://google.com") is False
    assert validation_service.validate_domain_syntax("") is False


def test_validate_public_suffix(validation_service: DomainValidationService):
    assert validation_service.validate_public_suffix("openai.com") is True
    assert validation_service.validate_public_suffix("startup.io") is True
    assert validation_service.validate_public_suffix("company.123") is False


def test_is_suspicious_domain_enterprise_mismatch(validation_service: DomainValidationService):
    # IBM should resolve to ibm.com, not ibmadison.com
    suspicious, reason = validation_service.is_suspicious_domain("IBM", "ibmadison.com")
    assert suspicious is True
    assert "Brand mismatch" in reason or "Suspicious suffix" in reason

    # Canonical match should pass
    suspicious_valid, _ = validation_service.is_suspicious_domain("IBM", "ibm.com")
    assert suspicious_valid is False


def test_is_suspicious_domain_parked_keywords(validation_service: DomainValidationService):
    suspicious, reason = validation_service.is_suspicious_domain("MyCompany", "mycompany-domainfor-sale.com")
    assert suspicious is True
    assert "parked/suspicious keyword" in reason


@pytest.mark.asyncio
async def test_validate_resolved_domain_pipeline(validation_service: DomainValidationService):
    # Valid domain
    res_valid = await validation_service.validate_resolved_domain("Google", "google.com", verify_dns=False)
    assert res_valid.is_valid is True
    assert res_valid.rejection_reason is None

    # Rejected IBM -> ibmadison.com
    res_ibm = await validation_service.validate_resolved_domain("IBM", "ibmadison.com", verify_dns=False)
    assert res_ibm.is_valid is False
    assert res_ibm.is_suspicious is True
    assert res_ibm.rejection_reason is not None

    # Invalid syntax
    res_invalid = await validation_service.validate_resolved_domain("BadName", "not_a_domain", verify_dns=False)
    assert res_invalid.is_valid is False
    assert res_invalid.syntax_valid is False

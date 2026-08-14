"""Automated test suite verifying Phase 6 Export Engine, Analytics Platform, Dashboard APIs, and Real Email Verification Provider."""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.config.settings import settings
from app.services.export_service import ExportService
from app.services.verification_scoring_service import VerificationScoringService
from app.providers.email_verification.smtp_provider import SmtpEmailVerificationProvider
from app.providers.email_verification.provider_registry import ProviderRegistry


@pytest.fixture
def client() -> TestClient:
    """TestClient fixture for FastAPI app testing."""
    return TestClient(app)


def test_verification_scoring_service():
    """Test VerificationScoringService composite score calculation."""
    score_high = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.9,
        mx_valid=True,
        smtp_valid=True,
        is_catch_all=False,
        is_disposable=False,
        is_role_account=False,
    )
    assert score_high == 96.0

    score_disposable = VerificationScoringService.calculate_composite_score(
        pattern_confidence=0.8,
        mx_valid=True,
        smtp_valid=False,
        is_catch_all=False,
        is_disposable=True,
        is_role_account=True,
    )
    assert score_disposable == 12.0


@pytest.mark.asyncio
async def test_smtp_provider_disposable_and_role_detection():
    """Test SmtpEmailVerificationProvider disposable and role account detection logic."""
    provider = SmtpEmailVerificationProvider()

    assert provider._is_disposable_domain("mailinator.com") is True
    assert provider._is_disposable_domain("google.com") is False

    assert provider._is_role_account("support") is True
    assert provider._is_role_account("john.doe") is False

    # Test verify for disposable email
    res_disp = await provider.verify("user@mailinator.com")
    assert res_disp["is_disposable"] is True
    assert res_disp["status"] == "invalid"


def test_provider_registry_contains_smtp():
    """Test that ProviderRegistry includes registered 'smtp' provider."""
    providers = ProviderRegistry.list_providers()
    assert "smtp" in providers
    assert "mock" in providers


@pytest.mark.asyncio
async def test_export_service_filtering_and_formats():
    """Test ExportService formatting and filter parameters (full, top_ranked_only, successful_only, failed_only)."""
    job_id = uuid4()
    mock_job = MagicMock()
    mock_job.original_filename = "test_data.csv"

    mock_res_success = MagicMock()
    mock_res_success.row_number = 1
    mock_res_success.company = "Stripe"
    mock_res_success.resolved_domain = "stripe.com"
    mock_res_success.provider = "Brandfetch"
    mock_res_success.cached = True
    mock_res_success.success = True
    mock_res_success.processed_at = None

    mock_res_fail = MagicMock()
    mock_res_fail.row_number = 2
    mock_res_fail.company = "UnknownCorp"
    mock_res_fail.resolved_domain = None
    mock_res_fail.provider = None
    mock_res_fail.cached = False
    mock_res_fail.success = False
    mock_res_fail.processed_at = None

    job_repo = MagicMock()
    job_repo.get_by_id.return_value = mock_job

    result_repo = MagicMock()
    result_repo.get_by_job_id.return_value = [mock_res_success, mock_res_fail]

    cand_repo = MagicMock()
    cand_repo.get_by_job_id.return_value = []

    export_service = ExportService(job_repo=job_repo, job_result_repo=result_repo, candidate_repo=cand_repo)

    # Test full filter
    _, full_recs = export_service.get_export_records(job_id, export_filter="full")
    assert len(full_recs) == 2

    # Test successful_only filter
    _, succ_recs = export_service.get_export_records(job_id, export_filter="successful_only")
    assert len(succ_recs) == 1
    assert succ_recs[0]["Company Name"] == "Stripe"

    # Test failed_only filter
    _, fail_recs = export_service.get_export_records(job_id, export_filter="failed_only")
    assert len(fail_recs) == 1
    assert fail_recs[0]["Company Name"] == "UnknownCorp"

    # Test CSV export byte generation
    filename, media_type, content_bytes = export_service.generate_export(job_id, export_format="csv")
    assert filename == "test_data_export.csv"
    assert media_type == "text/csv"
    assert b"Stripe" in content_bytes

    # Test Excel XLSX export byte generation
    filename_x, media_type_x, content_x = export_service.generate_export(job_id, export_format="xlsx")
    assert filename_x == "test_data_export.xlsx"
    assert media_type_x == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(content_x) > 0


def test_analytics_and_dashboard_endpoints(client: TestClient):
    """Test Analytics and Dashboard REST endpoints."""
    res_jobs = client.get("/api/v1/analytics/jobs")
    assert res_jobs.status_code == 200
    assert "total_jobs" in res_jobs.json()

    res_workers = client.get("/api/v1/analytics/workers")
    assert res_workers.status_code == 200
    assert "total_active_workers" in res_workers.json()

    res_providers = client.get("/api/v1/analytics/providers")
    assert res_providers.status_code == 200
    assert "brandfetch" in res_providers.json()

    res_cache = client.get("/api/v1/analytics/cache")
    assert res_cache.status_code == 200
    assert "cached_domains_total" in res_cache.json()

    res_overview = client.get("/api/v1/dashboard/overview")
    assert res_overview.status_code == 200
    assert "jobs_summary" in res_overview.json()

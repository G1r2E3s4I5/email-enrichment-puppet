"""Comprehensive unit and integration tests for Phase 5 Production Platform, Reporting, Exports, and Monitoring."""

import io
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import ProcessingJob
from app.models.job_result import JobResult
from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.services.export_service import sanitize_export_filename

client = TestClient(app)


@pytest.fixture
def setup_test_job_data():
    """Fixture populating a test processing job, results, and candidate records."""
    job_repo = JobRepository()
    job_result_repo = JobResultRepository()
    candidate_repo = GeneratedEmailCandidateRepository()

    job_id = uuid4()
    now = datetime.now(timezone.utc)
    job = ProcessingJob(
        id=job_id,
        original_filename="enterprise_leads_v1.csv",
        stored_filename="uploads/enterprise_leads_v1.csv",
        file_size=1024,
        total_rows=2,
        processed_rows=2,
        successful_rows=2,
        failed_rows=0,
        status="COMPLETED",
        created_at=now,
        completed_at=now,
    )
    job_repo.create_job(job)

    res1 = JobResult(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        company="Stripe",
        resolved_domain="stripe.com",
        provider="Brandfetch",
        cached=False,
        success=True,
    )
    res2 = JobResult(
        id=uuid4(),
        job_id=job_id,
        row_number=2,
        company="OpenAI",
        resolved_domain="openai.com",
        provider="Cache",
        cached=True,
        success=True,
    )
    job_result_repo.insert_result(res1)
    job_result_repo.insert_result(res2)

    cand1 = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        candidate_email="john.doe@stripe.com",
        pattern_name="first.last",
        confidence_score=0.95,
        pattern_score=0.9,
        final_score=0.95,
        rank=1,
        verification_status="valid",
        verification_confidence=96.0,
        verification_provider="Mock",
    )
    cand2 = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=2,
        candidate_email="contact@openai.com",
        pattern_name="generic",
        confidence_score=0.85,
        pattern_score=0.8,
        final_score=0.85,
        rank=1,
        verification_status="valid",
        verification_confidence=90.0,
        verification_provider="Mock",
    )
    candidate_repo.insert_candidate(cand1)
    candidate_repo.insert_candidate(cand2)

    return job_id


def test_filename_sanitization():
    """Test path traversal security sanitization for export filenames."""
    assert sanitize_export_filename("../../../etc/passwd.csv") == "passwd.csv"
    assert sanitize_export_filename("my_leads/../file.csv") == "file.csv"
    assert sanitize_export_filename("normal_file.csv") == "normal_file.csv"


def test_list_jobs_dashboard_pagination_and_filtering(setup_test_job_data):
    """Test GET /api/v1/jobs dashboard listing, filtering, and pagination."""
    response = client.get("/api/v1/jobs?limit=10&offset=0&status=COMPLETED")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_get_job_statistics(setup_test_job_data):
    """Test GET /api/v1/jobs/{job_id}/statistics endpoint."""
    job_id = setup_test_job_data
    response = client.get(f"/api/v1/jobs/{job_id}/statistics")
    assert response.status_code == 200
    data = response.json()

    assert data["job_id"] == str(job_id)
    assert data["status"] == "COMPLETED"
    assert data["processed_rows"] == 2
    assert data["companies_resolved"] == 2
    assert data["cache_hit_count"] == 1
    assert data["cache_hit_rate"] == 50.0
    assert data["verification_success_rate"] == 100.0
    assert data["total_candidates_generated"] >= 2


def test_get_job_error_report(setup_test_job_data):
    """Test GET /api/v1/jobs/{job_id}/errors endpoint."""
    job_id = setup_test_job_data
    response = client.get(f"/api/v1/jobs/{job_id}/errors")
    assert response.status_code == 200
    data = response.json()

    assert data["job_id"] == str(job_id)
    assert "failed_rows" in data
    assert "failed_companies" in data
    assert "verification_failures" in data


def test_export_csv_xlsx_json(setup_test_job_data):
    """Test exporting job results in CSV, XLSX, and JSON formats."""
    job_id = setup_test_job_data

    # CSV Export
    csv_res = client.get(f"/api/v1/jobs/{job_id}/export?format=csv")
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    assert "Job ID" in csv_res.text
    assert "Stripe" in csv_res.text

    # XLSX Export
    xlsx_res = client.get(f"/api/v1/jobs/{job_id}/export?format=xlsx")
    assert xlsx_res.status_code == 200
    assert xlsx_res.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert len(xlsx_res.content) > 100

    # JSON Export
    json_res = client.get(f"/api/v1/jobs/{job_id}/export?format=json")
    assert json_res.status_code == 200
    assert json_res.headers["content-type"].startswith("application/json")
    json_data = json_res.json()
    assert isinstance(json_data, list)
    assert len(json_data) >= 2


def test_platform_analytics_dashboard(setup_test_job_data):
    """Test GET /api/v1/analytics/dashboard platform-wide analytics."""
    response = client.get("/api/v1/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()

    assert "total_jobs" in data
    assert "jobs_by_status" in data
    assert "total_companies_processed" in data
    assert "verification_success_rate" in data
    assert "provider_usage_breakdown" in data


def test_worker_stats_monitoring_and_psutil_metrics():
    """Test GET /api/v1/workers/stats worker monitoring and psutil metrics."""
    response = client.get("/api/v1/workers/stats")
    assert response.status_code == 200
    data = response.json()

    assert "worker_status" in data
    assert "queue_length" in data
    assert "system_metrics" in data
    sys_m = data["system_metrics"]
    assert "cpu_percent" in sys_m
    assert "memory_mb" in sys_m
    assert "memory_percent" in sys_m

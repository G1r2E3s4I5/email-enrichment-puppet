"""Unit tests for JobResultRepository."""

from datetime import datetime, timezone
from uuid import uuid4
import pytest

from app.database.repositories.job_result_repository import JobResultRepository
from app.models.job_result import JobResult


def test_job_result_repository_memory_fallback() -> None:
    """Test JobResultRepository memory fallback when Supabase client is None."""
    repo = JobResultRepository(client=None)
    job_uuid = uuid4()

    res1 = JobResult(
        id=uuid4(),
        job_id=job_uuid,
        row_number=1,
        company="Stripe",
        resolved_domain="stripe.com",
        provider="Brandfetch",
        cached=False,
        success=True,
        error_message=None,
        processed_at=datetime.now(timezone.utc),
    )

    res2 = JobResult(
        id=uuid4(),
        job_id=job_uuid,
        row_number=2,
        company="Unknown Co",
        resolved_domain=None,
        provider=None,
        cached=False,
        success=False,
        error_message="Domain not found",
        processed_at=datetime.now(timezone.utc),
    )

    repo.insert_result(res1)
    repo.insert_result(res2)

    results = repo.get_results_by_job_id(job_uuid)
    assert len(results) == 2
    assert results[0].company == "Stripe"
    assert results[0].success is True
    assert results[1].company == "Unknown Co"
    assert results[1].success is False

    summary = repo.get_summary_by_job_id(job_uuid)
    assert summary["total_rows"] == 2
    assert summary["successful_rows"] == 1
    assert summary["failed_rows"] == 1

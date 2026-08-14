"""Integration tests for email patterns and candidate REST API endpoints."""

from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.api.dependencies.services import get_generated_candidate_repository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository

client = TestClient(app)


def test_get_email_patterns_endpoint() -> None:
    """Test GET /api/v1/email-patterns returns supported patterns metadata list."""
    response = client.get("/api/v1/email-patterns")
    assert response.status_code == 200
    data = response.json()
    assert "total_patterns" in data
    assert "patterns" in data
    assert data["total_patterns"] >= 20
    assert len(data["patterns"]) == data["total_patterns"]

    first_pat = data["patterns"][0]
    assert "pattern_name" in first_pat
    assert "template" in first_pat
    assert "base_confidence" in first_pat
    assert "example" in first_pat


def test_get_job_email_candidates_endpoint() -> None:
    """Test GET /api/v1/jobs/{job_id}/email-candidates endpoint with dependency override."""
    job_id = uuid4()
    repo = GeneratedEmailCandidateRepository(client=None)

    # Seed mock candidate record
    cand = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        candidate_email="sam.altman@openai.com",
        pattern_name="first.last",
        confidence_score=0.95,
    )
    repo.insert_candidate(cand)

    app.dependency_overrides[get_generated_candidate_repository] = lambda: repo
    try:
        response = client.get(f"/api/v1/jobs/{job_id}/email-candidates")
        assert response.status_code == 200
        data = response.json()

        assert data["job_id"] == str(job_id)
        assert data["total_candidates"] >= 1
        assert data["candidates"][0]["candidate_email"] == "sam.altman@openai.com"
        assert data["candidates"][0]["pattern_name"] == "first.last"
        assert data["candidates"][0]["confidence_score"] == 0.95
    finally:
        app.dependency_overrides.clear()

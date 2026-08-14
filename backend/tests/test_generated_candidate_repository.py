"""Unit tests for GeneratedEmailCandidateRepository."""

from uuid import uuid4
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.models.generated_email_candidate import GeneratedEmailCandidate


def test_repository_insert_and_retrieval_memory_fallback() -> None:
    """Test candidate repository insertion and retrieval using memory fallback store."""
    repo = GeneratedEmailCandidateRepository(client=None)
    job_id = uuid4()

    c1 = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        candidate_email="sam.altman@openai.com",
        pattern_name="first.last",
        confidence_score=0.95,
    )
    c2 = GeneratedEmailCandidate(
        id=uuid4(),
        job_id=job_id,
        row_number=1,
        candidate_email="saltman@openai.com",
        pattern_name="firstinitiallastname",
        confidence_score=0.90,
    )

    repo.bulk_insert_candidates([c1, c2])

    results = repo.get_candidates_by_job_id(job_id)
    assert len(results) == 2
    assert results[0].candidate_email == "sam.altman@openai.com"
    assert results[1].candidate_email == "saltman@openai.com"

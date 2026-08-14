"""End-to-end runtime verification test suite for Phase 4.2 Email Verification Pipeline."""

import pytest
import os
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import ProcessingJob
from app.schemas.queue import JobQueuePayload
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.workers.enrichment_worker import EnrichmentWorker
from app.services.csv_upload_service import CSVUploadService


from unittest.mock import patch
from app.config.settings import settings


@pytest.mark.asyncio
async def test_e2e_phase_4_2_pipeline_runtime_verification():
    """Execute end-to-end CSV upload -> queue -> worker execution -> verification -> DB query -> REST API audit."""
    with patch.object(settings, "EMAIL_VERIFICATION_PROVIDER", "mock"), patch.object(settings, "EMAIL_VERIFICATION_MODE", "mock"):
        GeneratedEmailCandidateRepository._shared_memory_candidates.clear()

        job_repo = JobRepository(client=None)
        candidate_repo = GeneratedEmailCandidateRepository(client=None)
        upload_service = CSVUploadService()

        # Create dummy CSV on disk
        test_filename = f"test_e2e_phase42_{uuid4().hex[:8]}.csv"
        file_path = os.path.join(upload_service.upload_dir, test_filename)

        csv_content = (
            "Company,First Name,Last Name\n"
            "Stripe,John,Smith\n"
            "OpenAI,Sam,Altman\n"
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        job_id = uuid4()
        job_entity = ProcessingJob(
            id=job_id,
            original_filename=test_filename,
            stored_filename=test_filename,
            file_size=len(csv_content),
            total_rows=2,
            status="VALIDATED",
            created_at=datetime.now(timezone.utc),
        )
        job_repo.create_job(job_entity)

        # Instantiate worker
        worker = EnrichmentWorker(
            job_repository=job_repo,
            candidate_repository=candidate_repo,
            upload_service=upload_service,
        )

        payload = JobQueuePayload(
            job_id=str(job_id),
            stored_filename=test_filename,
            original_filename=test_filename,
            row_count=2,
            upload_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Process job via worker
        await worker.process_job(payload, job_start_clock=0.0)

        # Clean up test file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        # 1. Query database rows
        candidates = candidate_repo.get_candidates_by_job_id(job_id)
        assert len(candidates) > 0, "Candidate records must be generated and stored"

        # 2. Check row 1 candidates (Stripe - John Smith)
        row1_candidates = [c for c in candidates if c.row_number == 1]
        assert len(row1_candidates) > 0

        # Verify rank 1 candidate
        rank1 = row1_candidates[0]
        assert rank1.rank == 1, "Top candidate must have rank = 1"
        assert rank1.verification_status.upper() == "VALID"
        assert rank1.verification_confidence == 96.0
        assert rank1.verification_provider == "Mock"
        assert rank1.is_disposable is False

        # Verify rank ordering across remaining row 1 candidates
        for i in range(len(row1_candidates) - 1):
            c_current = row1_candidates[i]
            c_next = row1_candidates[i + 1]
            assert c_current.rank <= c_next.rank, "Candidates must be ordered by rank ASC"
            assert c_current.confidence_score >= c_next.confidence_score, "Rank 1 candidate must have highest quality final_score"

        # 3. Test REST API endpoint ordering and payload
        client = TestClient(app)
        response = client.get(f"/api/v1/jobs/{job_id}/email-candidates")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == str(job_id)
        assert data["total_candidates"] == len(candidates)

        api_cands = data["candidates"]
        assert api_cands[0]["rank"] == 1
        assert api_cands[0]["email"] == rank1.candidate_email
        assert "pattern_score" in api_cands[0]
        assert "final_score" in api_cands[0]
        assert "verification_status" in api_cands[0]
        assert "verification_confidence" in api_cands[0]
        assert "verification_provider" in api_cands[0]

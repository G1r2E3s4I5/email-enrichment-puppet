"""Automated End-to-End Integration Test for CSV Upload -> Job Creation -> Queueing -> Background Worker Flow."""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.services import get_domain_resolver_service
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.main import app
from app.schemas.domain_resolver import ResolverDomainResult
from app.schemas.queue import JobQueuePayload
from app.services.csv_upload_service import CSVUploadService
from app.workers.enrichment_worker import EnrichmentWorker

from unittest.mock import patch
from app.config.settings import settings

client = TestClient(app)


@pytest.mark.asyncio
async def test_end_to_end_upload_queue_worker_flow() -> None:
    """End-to-End Test: CSV Upload -> Job Created -> Queue Job -> Status QUEUED -> Worker Processing -> Status COMPLETED."""
    with patch.object(settings, "EMAIL_VERIFICATION_PROVIDER", "mock"), patch.object(settings, "EMAIL_VERIFICATION_MODE", "mock"):
        # Step 1: Mock DomainResolverService for predictable fast results
        mock_domain_resolver = MagicMock()
        mock_domain_resolver.resolve_domain = AsyncMock(
            side_effect=lambda company: ResolverDomainResult(
                success=True,
                company=company,
                domain=f"{company.lower().replace(' ', '')}.com",
                provider="Brandfetch",
                cached=False,
                confidence=0.95,
                error=None,
            )
        )
        mock_domain_resolver.resolve_domains_batch = AsyncMock(
            side_effect=lambda companies, **kwargs: [
                ResolverDomainResult(
                    success=True,
                    company=c,
                    domain=f"{c.lower().replace(' ', '')}.com",
                    provider="Brandfetch",
                    cached=False,
                    confidence=0.95,
                    error=None,
                )
                for c in companies
            ]
        )

        app.dependency_overrides[get_domain_resolver_service] = lambda: mock_domain_resolver

        try:
            # 1. Upload CSV
            csv_content = b"Company,Website\nStripe,\nOpenAI,\nGitHub,\n"
            upload_resp = client.post(
                "/api/v1/jobs/upload",
                files={"file": ("test_companies.csv", csv_content, "text/csv")},
            )

            assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
            upload_data = upload_resp.json()
            job_id_str = upload_data["job_id"]
            job_uuid = UUID(job_id_str)
            stored_filename = upload_data["stored_filename"]
            assert upload_data["status"] == "VALIDATED"
            assert upload_data["rows"] == 3

            # 2. Verify job detail immediately after upload
            detail_resp1 = client.get(f"/api/v1/jobs/{job_id_str}")
            assert detail_resp1.status_code == 200, f"Get detail failed: {detail_resp1.text}"
            assert detail_resp1.json()["status"] == "VALIDATED"

            # 3. Queue Job in Redis
            queue_resp = client.post(f"/api/v1/jobs/{job_id_str}/queue")
            assert queue_resp.status_code == 200, f"Queue job failed: {queue_resp.text}"
            queue_data = queue_resp.json()
            assert queue_data["success"] is True
            assert queue_data["status"] == "QUEUED"

            # 4. Verify job status updated to QUEUED in database/memory
            detail_resp2 = client.get(f"/api/v1/jobs/{job_id_str}")
            assert detail_resp2.status_code == 200
            assert detail_resp2.json()["status"] in ("QUEUED", "PROCESSING")

            # 5. Process job using EnrichmentWorker
            from app.database.supabase import get_supabase_client
            db = get_supabase_client()
            job_repo = JobRepository(client=db)
            result_repo = JobResultRepository(client=db)
            upload_service = CSVUploadService()

            worker = EnrichmentWorker(
                redis_queue_service=MagicMock(),
                domain_resolver_service=mock_domain_resolver,
                job_repository=job_repo,
                job_result_repository=result_repo,
                upload_service=upload_service,
            )

            payload = JobQueuePayload(
                job_id=job_id_str,
                stored_filename=stored_filename,
                original_filename="test_companies.csv",
                upload_timestamp=datetime.now(timezone.utc).isoformat(),
                row_count=3,
                metadata={},
            )

            import time
            await worker.process_job(payload, time.perf_counter())

            # 6. Verify final completed state and telemetry
            final_detail = client.get(f"/api/v1/jobs/{job_id_str}")
            assert final_detail.status_code == 200
            final_data = final_detail.json()

            assert final_data["status"] == "COMPLETED"
            assert final_data["total_rows"] == 3
            assert final_data["processed_rows"] == 3
            assert final_data["successful_rows"] == 3
            assert final_data["failed_rows"] == 0

        finally:
            app.dependency_overrides.clear()

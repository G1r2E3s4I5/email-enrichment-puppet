"""End-to-End Integration Test for Upload -> Queue -> Worker -> Cache Pipeline."""

import pytest
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from app.main import app
from app.api.dependencies.services import (
    get_job_service,
    get_redis_queue_service,
)
from app.models.job import ProcessingJob
from app.schemas.queue import JobQueuePayload
from app.services.domain_resolver_service import DomainResolverService
from app.services.job_service import JobService


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_redis_queue():
    queue = MagicMock()
    queue.get_queue_size.return_value = 0
    queue.enqueue_job.return_value = 1
    queue.health_check.return_value = MagicMock(connected=True)
    return queue


@pytest.mark.asyncio
async def test_e2e_upload_queue_worker_cache_pipeline(test_client: TestClient, mock_redis_queue):
    # 1. Setup Mock Repositories
    mock_job_repo = MagicMock()
    created_jobs = {}

    def fake_create_job(job_entity: ProcessingJob):
        created_jobs[str(job_entity.id)] = job_entity
        return job_entity

    def fake_get_by_id(job_id: UUID):
        return created_jobs.get(str(job_id))

    def fake_update_job(job_id: UUID, updates: dict):
        if str(job_id) in created_jobs:
            for k, v in updates.items():
                setattr(created_jobs[str(job_id)], k, v)

    mock_job_repo.create_job.side_effect = fake_create_job
    mock_job_repo.get_by_id.side_effect = fake_get_by_id
    mock_job_repo.update_job.side_effect = fake_update_job

    real_job_service = JobService(
        job_repository=mock_job_repo,
        redis_queue_service=mock_redis_queue,
    )

    # Set dependency overrides BEFORE upload and queue calls
    app.dependency_overrides[get_redis_queue_service] = lambda: mock_redis_queue
    app.dependency_overrides[get_job_service] = lambda: real_job_service

    try:
        mock_company_repo = MagicMock()
        mock_company_repo.get_by_normalized_name.return_value = None

        mock_brandfetch = MagicMock()
        bf_res = MagicMock()
        bf_res.success = True
        bf_res.domain = "stripe.com"
        bf_res.confidence = 90.0
        mock_brandfetch.resolve_domain = AsyncMock(return_value=bf_res)

        # 2. Upload CSV via REST API
        csv_bytes = b"Company,First Name,Last Name\nStripe,John,Doe\n"
        response = test_client.post(
            "/api/v1/jobs/upload",
            files={"file": ("valid_companies.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == 201
        upload_data = response.json()
        returned_job_id = upload_data["job_id"]

        # Verify real returned job ID is NOT the Swagger example UUID
        assert returned_job_id != "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        assert UUID(returned_job_id)

        # 3. Queue using the EXACT returned job_id
        queue_resp = test_client.post(f"/api/v1/jobs/{returned_job_id}/queue")
        assert queue_resp.status_code == 200
        q_data = queue_resp.json()
        assert q_data["success"] is True
        assert q_data["job_id"] == returned_job_id
        assert q_data["status"] == "QUEUED"

        # Verify Redis enqueue was called with exact same job_id
        mock_redis_queue.enqueue_job.assert_called_once()
        payload: JobQueuePayload = mock_redis_queue.enqueue_job.call_args[0][0]
        assert payload.job_id == returned_job_id

        # 4. Worker Dequeues & Processes Job (Resolution Flow)
        domain_service = DomainResolverService(
            company_domain_repo=mock_company_repo,
            brandfetch_provider=mock_brandfetch,
        )

        # First domain resolution for "Stripe" -> Cache MISS -> Brandfetch called
        res1 = await domain_service.resolve_domain("Stripe")
        assert res1.success is True
        assert res1.domain == "stripe.com"
        assert res1.cached is False
        mock_brandfetch.resolve_domain.assert_called_once_with("Stripe")

        # Second domain resolution for "Stripe" (Cache HIT simulation)
        mock_company_repo.get_by_normalized_name.return_value = MagicMock(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            domain="stripe.com",
            confidence=95.0,
            created_at=None,
        )
        mock_brandfetch.resolve_domain.reset_mock()

        res2 = await domain_service.resolve_domain("Stripe")
        assert res2.success is True
        assert res2.domain == "stripe.com"
        assert res2.cached is True
        # Verify Brandfetch was SKIPPED on second resolution due to Cache HIT
        mock_brandfetch.resolve_domain.assert_not_called()

    finally:
        # Reset overrides
        app.dependency_overrides.clear()

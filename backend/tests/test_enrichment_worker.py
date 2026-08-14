"""Unit and Integration Tests for Phase 2.4 Background Worker Engine."""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.main import app
from app.schemas.queue import JobQueuePayload
from app.services.enrichment_pipeline_service import EnrichmentPipelineService
from app.services.job_progress_service import JobProgressService
from app.workers.enrichment_worker import EnrichmentWorker
from app.workers.worker_manager import WorkerManager
from app.workers.worker_state import WorkerState

client = TestClient(app)


def test_worker_state_formatting() -> None:
    """Test WorkerState telemetry uptime formatting and dict serialization."""
    state = WorkerState()
    assert state.running is False
    assert state.get_uptime_formatted() == "0s"

    state.running = True
    assert state.running is True
    assert "s" in state.get_uptime_formatted()

    state.increment_processed_jobs()
    assert state.processed_jobs == 1
    assert state.last_activity is not None

    payload = state.to_dict(queue_size=3)
    assert payload["running"] is True
    assert payload["processed_jobs"] == 1
    assert payload["queue_size"] == 3


def test_enrichment_pipeline_service_placeholder_generation() -> None:
    """Test EnrichmentPipelineService domain and email candidate generation."""
    pipeline = EnrichmentPipelineService()

    domain = pipeline.generate_placeholder_domain("OpenAI Inc.")
    assert domain == "openaiinc.com"

    candidates = pipeline.generate_candidate_emails("openai.com", "Sam", "Altman")
    assert "sam@openai.com" in candidates
    assert "s.altman@openai.com" in candidates
    assert "saltman@openai.com" in candidates


def test_job_progress_service_calculation() -> None:
    """Test JobProgressService metrics calculation."""
    progress_svc = JobProgressService()
    start_time = 100.0

    metrics = progress_svc.calculate_metrics(
        current_row=5,
        total_rows=10,
        current_company="Stripe",
        job_start_time=start_time,
    )

    assert metrics["processed_rows"] == 5
    assert metrics["remaining_rows"] == 5
    assert metrics["progress_percentage"] == 50.0
    assert metrics["current_company"] == "Stripe"


@pytest.mark.asyncio
async def test_enrichment_worker_job_processing(tmp_path) -> None:
    """Test EnrichmentWorker popping job from Redis and executing full pipeline."""
    job_id = uuid4()
    stored_filename = "test_pipeline.csv"
    file_path = os.path.join(str(tmp_path), stored_filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Company,First Name,Last Name\nOpenAI,Sam,Altman\nStripe,Patrick,Collison\n")

    mock_queue_svc = MagicMock()
    mock_job_repo = MagicMock()
    mock_result_repo = MagicMock()
    mock_upload_svc = MagicMock()
    mock_upload_svc.upload_dir = str(tmp_path)

    worker = EnrichmentWorker(
        redis_queue_service=mock_queue_svc,
        job_repository=mock_job_repo,
        job_result_repository=mock_result_repo,
        upload_service=mock_upload_svc,
    )

    payload = JobQueuePayload(
        job_id=str(job_id),
        stored_filename=stored_filename,
        original_filename="companies.csv",
        upload_timestamp=datetime.now(timezone.utc).isoformat(),
        row_count=2,
        metadata={},
    )

    await worker.process_job(payload, job_start_clock=100.0)

    # Verify status transitions & DB updates
    assert mock_job_repo.update_job.call_count >= 2
    last_call = mock_job_repo.update_job.call_args_list[-1]
    assert last_call[0][0] == job_id
    assert last_call[0][1]["status"] == "COMPLETED"
    assert last_call[0][1]["processed_rows"] == 2
    assert last_call[0][1]["successful_rows"] == 2
    assert mock_result_repo.insert_result.call_count == 2


def test_worker_api_endpoints() -> None:
    """Test POST /start, POST /stop, GET /status endpoints."""
    resp_status = client.get("/api/v1/workers/status")
    assert resp_status.status_code == 200
    data = resp_status.json()
    assert "running" in data
    assert "processed_jobs" in data
    assert "queue_size" in data
    assert "uptime" in data

    resp_start = client.post("/api/v1/workers/start")
    assert resp_start.status_code == 200
    assert resp_start.json()["success"] is True

    resp_stop = client.post("/api/v1/workers/stop")
    assert resp_stop.status_code == 200
    assert resp_stop.json()["success"] is True

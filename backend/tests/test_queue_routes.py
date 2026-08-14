"""Integration tests for Redis Queue API endpoints."""

from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.services import get_job_service, get_redis_queue_service
from app.core.exceptions import (
    APIException,
    DuplicateRecordException,
    EntityNotFoundException,
)
from app.main import app
from app.schemas.queue import (
    JobQueuePayload,
    QueueJobResponse,
    QueueStatusResponse,
    RedisHealthStatus,
)

client = TestClient(app)


def test_queue_job_endpoint_success() -> None:
    """Test POST /api/v1/jobs/{job_id}/queue successfully queueing a job."""
    job_uuid = uuid4()
    mock_job_service = MagicMock()
    mock_job_service.queue_job.return_value = QueueJobResponse(
        success=True,
        job_id=str(job_uuid),
        status="QUEUED",
        queue_position=4,
    )

    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    try:
        response = client.post(f"/api/v1/jobs/{job_uuid}/queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == str(job_uuid)
        assert data["status"] == "QUEUED"
        assert data["queue_position"] == 4
    finally:
        app.dependency_overrides.clear()


def test_queue_job_endpoint_duplicate_error() -> None:
    """Test POST /api/v1/jobs/{job_id}/queue returning HTTP 400 for duplicate request."""
    job_uuid = uuid4()
    mock_job_service = MagicMock()
    mock_job_service.queue_job.side_effect = DuplicateRecordException(
        message=f"Processing job with ID '{job_uuid}' is already queued"
    )

    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    try:
        response = client.post(f"/api/v1/jobs/{job_uuid}/queue")

        assert response.status_code == 400
        data = response.json()
        assert "already queued" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_queue_job_endpoint_not_found_error() -> None:
    """Test POST /api/v1/jobs/{job_id}/queue returning HTTP 404 for unknown job ID."""
    job_uuid = uuid4()
    mock_job_service = MagicMock()
    mock_job_service.queue_job.side_effect = EntityNotFoundException(
        message=f"Processing job with ID '{job_uuid}' not found"
    )

    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    try:
        response = client.post(f"/api/v1/jobs/{job_uuid}/queue")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_queue_job_endpoint_redis_unavailable_error() -> None:
    """Test POST /api/v1/jobs/{job_id}/queue returning HTTP 503 when Redis is unavailable."""
    job_uuid = uuid4()
    mock_job_service = MagicMock()
    mock_job_service.queue_job.side_effect = APIException(
        message="Redis service unavailable: Connection refused",
        status_code=503,
    )

    app.dependency_overrides[get_job_service] = lambda: mock_job_service
    try:
        response = client.post(f"/api/v1/jobs/{job_uuid}/queue")

        assert response.status_code == 503
        data = response.json()
        assert "redis service unavailable" in data["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_get_queue_status_endpoint_success() -> None:
    """Test GET /api/v1/queue/status returning Redis health and queue metrics."""
    mock_queue_service = MagicMock()
    mock_queue_service.health_check.return_value = RedisHealthStatus(
        connected=True,
        latency_ms=1.25,
        ping=True,
        memory_used_human="1.02M",
        error=None,
    )
    mock_queue_service.get_queue_size.return_value = 2
    mock_queue_service.peek_queue.return_value = [
        JobQueuePayload(
            job_id="job-1",
            stored_filename="file1.csv",
            original_filename="leads.csv",
            upload_timestamp="2026-08-01T21:49:11+00:00",
            row_count=100,
            metadata={},
        ),
        JobQueuePayload(
            job_id="job-2",
            stored_filename="file2.csv",
            original_filename="companies.csv",
            upload_timestamp="2026-08-01T21:50:00+00:00",
            row_count=500,
            metadata={},
        ),
    ]

    app.dependency_overrides[get_redis_queue_service] = lambda: mock_queue_service
    try:
        response = client.get("/api/v1/queue/status")

        assert response.status_code == 200
        data = response.json()
        assert data["redis"]["connected"] is True
        assert data["redis"]["latency_ms"] == 1.25
        assert data["queue_size"] == 2
        assert len(data["waiting_jobs"]) == 2
        assert data["waiting_jobs"][0]["job_id"] == "job-1"
        assert data["waiting_jobs"][1]["job_id"] == "job-2"
    finally:
        app.dependency_overrides.clear()

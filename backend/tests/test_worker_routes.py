"""Integration tests for Worker API endpoints."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.services import get_worker_manager
from app.main import app
from app.schemas.worker import (
    WorkerStartResponse,
    WorkerStatusResponse,
    WorkerStopResponse,
)

client = TestClient(app)


def test_worker_status_endpoint() -> None:
    """Test GET /api/v1/workers/status returning status telemetry."""
    mock_status = WorkerStatusResponse(
        running=True,
        current_job="job-123",
        processed_jobs=3,
        queue_size=1,
        uptime="10s",
        last_activity="2026-08-02T23:20:00+00:00",
    )
    mock_manager = MagicMock()
    mock_manager.get_status.return_value = mock_status

    app.dependency_overrides[get_worker_manager] = lambda: mock_manager
    try:
        response = client.get("/api/v1/workers/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["current_job"] == "job-123"
        assert data["processed_jobs"] == 3
        assert data["queue_size"] == 1
    finally:
        app.dependency_overrides.clear()


def test_worker_start_endpoint() -> None:
    """Test POST /api/v1/workers/start launching background worker."""
    status = WorkerStatusResponse(
        running=True,
        current_job=None,
        processed_jobs=0,
        queue_size=0,
        uptime="0s",
        last_activity=None,
    )
    mock_manager = MagicMock()
    mock_manager.start_worker.return_value = WorkerStartResponse(
        success=True,
        message="Background worker started successfully",
        status=status,
    )

    app.dependency_overrides[get_worker_manager] = lambda: mock_manager
    try:
        response = client.post("/api/v1/workers/start")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "started" in data["message"].lower()
        assert data["status"]["running"] is True
    finally:
        app.dependency_overrides.clear()


def test_worker_stop_endpoint() -> None:
    """Test POST /api/v1/workers/stop stopping background worker."""
    status = WorkerStatusResponse(
        running=False,
        current_job=None,
        processed_jobs=1,
        queue_size=0,
        uptime="12s",
        last_activity="2026-08-02T23:20:00+00:00",
    )
    mock_manager = MagicMock()
    mock_manager.stop_worker.return_value = WorkerStopResponse(
        success=True,
        message="Background worker stop signal sent successfully",
        status=status,
    )

    app.dependency_overrides[get_worker_manager] = lambda: mock_manager
    try:
        response = client.post("/api/v1/workers/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stop" in data["message"].lower()
        assert data["status"]["running"] is False
    finally:
        app.dependency_overrides.clear()

"""Unit tests for WorkerManager lifecycle management."""

from unittest.mock import MagicMock
import pytest

from app.workers.enrichment_worker import EnrichmentWorker
from app.workers.worker_manager import WorkerManager
from app.workers.worker_state import WorkerState


def test_worker_manager_start_stop_status() -> None:
    """Test starting, status inspecting, and stopping WorkerManager."""
    mock_state = WorkerState()
    mock_worker = MagicMock(spec=EnrichmentWorker)
    mock_worker.state = mock_state

    manager = WorkerManager(worker=mock_worker)

    status = manager.get_status()
    assert status.running is False
    assert status.processed_jobs == 0

    start_res = manager.start_worker()
    assert start_res.success is True

    mock_state.running = True
    stop_res = manager.stop_worker()
    assert stop_res.success is True
    mock_worker.stop.assert_called_once()

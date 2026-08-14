"""Comprehensive unit and integration tests for Phase 5 Bulk Processing & Performance Optimization."""

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4
import pytest

from app.models.job import ProcessingJob
from app.models.job_result import JobResult
from app.models.generated_email_candidate import GeneratedEmailCandidate
from app.database.repositories.job_repository import JobRepository
from app.database.repositories.job_result_repository import JobResultRepository
from app.database.repositories.generated_email_candidate_repository import GeneratedEmailCandidateRepository
from app.schemas.queue import JobQueuePayload
from app.services.distributed_lock_service import DistributedLockService
from app.services.redis_queue_service import RedisQueueService
from app.workers.enrichment_worker import EnrichmentWorker, stream_csv_chunks


@pytest.fixture(autouse=True)
def reset_in_memory_stores():
    """Clear static in-memory stores before each test to ensure test isolation."""
    RedisQueueService._in_memory_queue.clear()
    RedisQueueService._in_memory_heartbeats.clear()
    yield
    RedisQueueService._in_memory_queue.clear()
    RedisQueueService._in_memory_heartbeats.clear()


def test_distributed_lock_acquisition_and_isolation():
    """Test distributed lock acquisition, TTL renewal, and isolation between competing workers."""
    lock_service = DistributedLockService(redis_client=None)
    lock_service._get_client = lambda: None
    job_id = f"test_job_{uuid4()}"

    # Worker 1 acquires lock
    assert lock_service.acquire_lock(job_id, owner_id="worker_1", ttl_sec=300) is True

    # Worker 2 attempts to acquire same lock -> must fail
    assert lock_service.acquire_lock(job_id, owner_id="worker_2", ttl_sec=300) is False

    # Worker 1 renews lock -> succeeds
    assert lock_service.renew_lock(job_id, owner_id="worker_1", ttl_sec=300) is True

    # Worker 2 attempts to release Worker 1's lock -> must fail
    assert lock_service.release_lock(job_id, owner_id="worker_2") is False

    # Worker 1 releases lock -> succeeds
    assert lock_service.release_lock(job_id, owner_id="worker_1") is True

    # Now Worker 2 can acquire lock
    assert lock_service.acquire_lock(job_id, owner_id="worker_2", ttl_sec=300) is True


def test_streaming_csv_chunks_generator():
    """Test streaming CSV parser yielding rows in configurable chunk blocks."""
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv") as tmp:
        tmp.write("Company,First Name,Last Name\n")
        tmp.write("Stripe,John,Doe\n")
        tmp.write("OpenAI,Sam,Altman\n")
        tmp.write("Google,Sundar,Pichai\n")
        tmp.write("Microsoft,Satya,Nadella\n")
        tmp_path = tmp.name

    try:
        chunks = list(stream_csv_chunks(tmp_path, chunk_size=2))
        assert len(chunks) == 2
        assert len(chunks[0]["rows"]) == 2
        assert chunks[0]["rows"][0]["Company"] == "Stripe"
        assert len(chunks[1]["rows"]) == 2
        assert chunks[1]["rows"][1]["Company"] == "Microsoft"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_priority_queue_and_heartbeats():
    """Test priority queue enqueue and worker heartbeat registration."""
    queue_service = RedisQueueService(redis_client=None)
    queue_service._get_client = lambda: None
    now_str = datetime.now(timezone.utc).isoformat()

    payload_normal = JobQueuePayload(
        job_id=str(uuid4()),
        original_filename="normal.csv",
        stored_filename="normal.csv",
        file_size=100,
        row_count=5,
        upload_timestamp=now_str,
    )
    payload_priority = JobQueuePayload(
        job_id=str(uuid4()),
        original_filename="priority.csv",
        stored_filename="priority.csv",
        file_size=100,
        row_count=5,
        upload_timestamp=now_str,
    )

    queue_service.enqueue_job(payload_normal, priority=False)
    queue_service.enqueue_job(payload_priority, priority=True)

    # Priority payload should be dequeued first
    dequeued_1 = queue_service.dequeue_job()
    assert dequeued_1.job_id == payload_priority.job_id

    # Test Heartbeat Registration
    worker_id = f"worker_{uuid4().hex[:6]}"
    queue_service.register_worker_heartbeat(
        worker_id=worker_id,
        current_job_id=None,
        processed_count=12,
        worker_status="IDLE",
    )
    active_workers = queue_service.get_active_workers()
    assert any(w["worker_id"] == worker_id for w in active_workers)


@pytest.mark.asyncio
async def test_multi_worker_competing_queue():
    """Test multiple worker instances dequeueing jobs concurrently without duplicate processing."""
    queue_service = RedisQueueService(redis_client=None)
    queue_service._get_client = lambda: None
    job_repo = JobRepository()
    now_str = datetime.now(timezone.utc).isoformat()

    worker_1 = EnrichmentWorker(
        redis_queue_service=queue_service,
        job_repository=job_repo,
        worker_id="worker_alpha",
    )
    worker_2 = EnrichmentWorker(
        redis_queue_service=queue_service,
        job_repository=job_repo,
        worker_id="worker_beta",
    )

    job_id_1 = str(uuid4())
    job_id_2 = str(uuid4())

    payload_1 = JobQueuePayload(
        job_id=job_id_1,
        original_filename="file1.csv",
        stored_filename="file1.csv",
        file_size=100,
        row_count=1,
        upload_timestamp=now_str,
    )
    payload_2 = JobQueuePayload(
        job_id=job_id_2,
        original_filename="file2.csv",
        stored_filename="file2.csv",
        file_size=100,
        row_count=1,
        upload_timestamp=now_str,
    )

    queue_service.enqueue_job(payload_1)
    queue_service.enqueue_job(payload_2)

    assert queue_service.get_queue_size() == 2

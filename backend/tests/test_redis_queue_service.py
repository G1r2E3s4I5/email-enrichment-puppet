"""Unit tests for RedisQueueService."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
import redis

from app.core.exceptions import (
    APIException,
    DatabaseException,
    DuplicateRecordException,
    ValidationException,
)
from app.schemas.queue import JobQueuePayload
from app.services.redis_queue_service import RedisQueueService


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client fixture."""
    client = MagicMock(spec=redis.Redis)
    client.ping.return_value = True
    return client


@pytest.fixture
def queue_service(mock_redis: MagicMock) -> RedisQueueService:
    """RedisQueueService instance with mocked Redis client."""
    return RedisQueueService(redis_client=mock_redis, queue_name="test_email_jobs")


def test_redis_connection_success(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test successful Redis connection verification."""
    assert queue_service.connect() is True
    mock_redis.ping.assert_called_once()


def test_redis_connection_failure(mock_redis: MagicMock) -> None:
    """Test Redis connection failure."""
    mock_redis.ping.side_effect = redis.ConnectionError("Connection refused")
    service = RedisQueueService(redis_client=mock_redis)
    assert service.connect() is False


def test_enqueue_job_success(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test successful enqueuing of a job payload."""
    mock_redis.lrange.return_value = []
    mock_redis.rpush.return_value = 1

    payload = JobQueuePayload(
        job_id="11111111-2222-3333-4444-555555555555",
        stored_filename="upload_123.csv",
        original_filename="companies.csv",
        upload_timestamp=datetime.now(timezone.utc).isoformat(),
        row_count=50,
        metadata={"headers": ["Company", "Website"]},
    )

    position = queue_service.enqueue_job(payload)
    assert position == 1
    mock_redis.rpush.assert_called_once()
    args, _ = mock_redis.rpush.call_args
    assert args[0] == "test_email_jobs"
    assert "11111111-2222-3333-4444-555555555555" in args[1]
    assert "companies.csv" in args[1]


def test_enqueue_job_duplicate_error(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test enqueuing duplicate job_id raises DuplicateRecordException."""
    existing_payload_str = (
        '{"job_id": "dup-job-id-123", "stored_filename": "f.csv", '
        '"original_filename": "f.csv", "upload_timestamp": "2026-08-01T00:00:00", '
        '"row_count": 10, "metadata": {}}'
    )
    mock_redis.lrange.return_value = [existing_payload_str]

    payload = JobQueuePayload(
        job_id="dup-job-id-123",
        stored_filename="f2.csv",
        original_filename="f2.csv",
        upload_timestamp=datetime.now(timezone.utc).isoformat(),
        row_count=10,
        metadata={},
    )

    with pytest.raises(DuplicateRecordException) as exc_info:
        queue_service.enqueue_job(payload)

    assert "already queued" in str(exc_info.value)


def test_enqueue_job_redis_unavailable(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test enqueuing when Redis raises ConnectionError."""
    mock_redis.lrange.return_value = []
    mock_redis.rpush.side_effect = redis.ConnectionError("Redis down")

    payload = JobQueuePayload(
        job_id="job-999",
        stored_filename="test.csv",
        original_filename="test.csv",
        upload_timestamp=datetime.now(timezone.utc).isoformat(),
        row_count=5,
        metadata={},
    )

    with pytest.raises(APIException) as exc_info:
        queue_service.enqueue_job(payload)

    assert exc_info.value.status_code == 503
    assert "Redis connection failure" in str(exc_info.value)



def test_dequeue_job_success(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test popping next job payload from front of Redis queue."""
    json_str = (
        '{"job_id": "pop-123", "stored_filename": "pop.csv", '
        '"original_filename": "pop.csv", "upload_timestamp": "2026-08-01T00:00:00", '
        '"row_count": 12, "metadata": {}}'
    )
    mock_redis.lpop.return_value = json_str

    popped = queue_service.dequeue_job()
    assert popped is not None
    assert popped.job_id == "pop-123"
    assert popped.row_count == 12


def test_dequeue_job_empty_queue(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test popping from empty queue returns None."""
    mock_redis.lpop.return_value = None
    assert queue_service.dequeue_job() is None


def test_peek_queue_and_size(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test peeking waiting jobs and checking queue size."""
    mock_redis.llen.return_value = 2
    mock_redis.lrange.return_value = [
        '{"job_id": "j1", "stored_filename": "1.csv", "original_filename": "1.csv", "upload_timestamp": "2026-08-01T00:00:00", "row_count": 5, "metadata": {}}',
        '{"job_id": "j2", "stored_filename": "2.csv", "original_filename": "2.csv", "upload_timestamp": "2026-08-01T00:00:00", "row_count": 8, "metadata": {}}',
    ]

    assert queue_service.get_queue_size() == 2
    jobs = queue_service.peek_queue(limit=5)
    assert len(jobs) == 2
    assert jobs[0].job_id == "j1"
    assert jobs[1].job_id == "j2"


def test_remove_job_success(queue_service: RedisQueueService, mock_redis: MagicMock) -> None:
    """Test removing job from queue by job_id."""
    raw_item = '{"job_id": "target-id", "stored_filename": "t.csv", "original_filename": "t.csv", "upload_timestamp": "2026-08-01T00:00:00", "row_count": 1, "metadata": {}}'
    mock_redis.lrange.return_value = [raw_item]
    mock_redis.lrem.return_value = 1

    res = queue_service.remove_job("target-id")
    assert res is True
    mock_redis.lrem.assert_called_once_with("test_email_jobs", 1, raw_item)

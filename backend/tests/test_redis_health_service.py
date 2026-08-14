"""Unit tests for RedisHealthService."""

from unittest.mock import MagicMock
import pytest
import redis

from app.services.redis_health_service import RedisHealthService


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client fixture."""
    client = MagicMock(spec=redis.Redis)
    client.ping.return_value = True
    client.info.return_value = {"used_memory_human": "2.45M"}
    return client


def test_redis_health_check_healthy(mock_redis: MagicMock) -> None:
    """Test health check when Redis is operational."""
    health_service = RedisHealthService(redis_client=mock_redis)
    health = health_service.check_health()

    assert health.connected is True
    assert health.ping is True
    assert health.latency_ms is not None
    assert health.latency_ms >= 0.0
    assert health.memory_used_human == "2.45M"
    assert health.error is None


def test_redis_health_check_connection_error(mock_redis: MagicMock) -> None:
    """Test health check when Redis raises connection error."""
    mock_redis.ping.side_effect = redis.ConnectionError("Connection refused to 127.0.0.1:6379")
    health_service = RedisHealthService(redis_client=mock_redis)

    health = health_service.check_health()

    assert health.connected is False
    assert health.ping is False
    assert health.latency_ms is None
    assert health.memory_used_human is None
    assert health.error is not None
    assert "Connection refused" in health.error


def test_redis_health_check_timeout_error(mock_redis: MagicMock) -> None:
    """Test health check when Redis socket times out."""
    mock_redis.ping.side_effect = redis.TimeoutError("Socket timeout")
    health_service = RedisHealthService(redis_client=mock_redis)

    health = health_service.check_health()

    assert health.connected is False
    assert health.ping is False
    assert health.error is not None
    assert "Socket timeout" in health.error

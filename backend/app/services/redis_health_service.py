"""Redis health monitoring service verifying connection, latency, ping, and memory metrics."""

import time
from typing import Optional
import redis

from app.config.logging import logger
from app.config.settings import settings
from app.schemas.queue import RedisHealthStatus


class RedisHealthService:
    """Service verifying Redis health metrics, connection, latency, and memory stats."""

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        """Initialize RedisHealthService with injected or default Redis client."""
        self._client = redis_client

    def _get_client(self) -> redis.Redis:
        """Get or initialize Redis client instance from settings."""
        if self._client is not None:
            return self._client

        from app.api.dependencies.services import get_redis_client
        client = get_redis_client()
        if client is not None:
            self._client = client
            return self._client

        use_url = False
        if settings.REDIS_URL:
            use_url = True
            if "localhost" in settings.REDIS_URL or "127.0.0.1" in settings.REDIS_URL:
                if settings.REDIS_HOST not in ("localhost", "127.0.0.1"):
                    use_url = False

        if use_url:
            self._client = redis.Redis.from_url(
                settings.REDIS_URL,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
        else:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                decode_responses=True,
            )
        return self._client


    def check_health(self) -> RedisHealthStatus:
        """Execute Redis health check: ping latency, connection, and memory usage."""
        start_time = time.perf_counter()
        try:
            client = self._get_client()
            ping_success = bool(client.ping())
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            memory_used_human: Optional[str] = None
            try:
                info_mem = client.info(section="memory")
                if isinstance(info_mem, dict):
                    memory_used_human = str(info_mem.get("used_memory_human", "N/A"))
            except Exception as mem_exc:
                logger.warning(f"Could not retrieve Redis memory info: {str(mem_exc)}")

            logger.info(f"Redis Health Check SUCCESS - Latency: {latency_ms}ms, Ping: {ping_success}")

            return RedisHealthStatus(
                connected=ping_success,
                latency_ms=latency_ms if ping_success else None,
                ping=ping_success,
                memory_used_human=memory_used_human,
                error=None,
            )

        except (redis.ConnectionError, redis.TimeoutError, redis.AuthenticationError) as redis_err:
            logger.warning(f"Redis Health Check Connection Error: {str(redis_err)}")
            return RedisHealthStatus(
                connected=False,
                latency_ms=None,
                ping=False,
                memory_used_human=None,
                error=f"Redis connection failure: {str(redis_err)}",
            )
        except Exception as exc:
            logger.error(f"Unexpected error during Redis health check: {str(exc)}")
            return RedisHealthStatus(
                connected=False,
                latency_ms=None,
                ping=False,
                memory_used_human=None,
                error=f"Unexpected Redis error: {str(exc)}",
            )

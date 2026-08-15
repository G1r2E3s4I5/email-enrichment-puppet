"""Redis Queue Service managing enqueue, dequeue, peek, size, heartbeats, and worker telemetry operations."""

import json
import time
from typing import Dict, List, Optional, Any
import redis

from app.config.logging import logger
from app.config.settings import settings
from app.core.exceptions import (
    APIException,
    DatabaseException,
    DuplicateRecordException,
    ValidationException,
)
from app.schemas.queue import JobQueuePayload, RedisHealthStatus
from app.services.redis_health_service import RedisHealthService


class RedisQueueService:
    """Service handling asynchronous job queue operations powered by Redis lists with heartbeats and pipelining."""

    _in_memory_queue: List[JobQueuePayload] = []
    _in_memory_heartbeats: Dict[str, Dict[str, Any]] = {}

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        queue_name: Optional[str] = None,
        health_service: Optional[RedisHealthService] = None,
    ) -> None:
        """Initialize RedisQueueService with client, queue name, and health monitoring service."""
        self._client = redis_client
        self._queue_name = queue_name or settings.REDIS_QUEUE_NAME
        self._health_service = health_service or RedisHealthService(redis_client=redis_client)

    def _get_client(self) -> redis.Redis:
        """Retrieve configured Redis client instance."""
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

    @property
    def queue_name(self) -> str:
        """Current Redis queue key name."""
        return self._queue_name

    def connect(self) -> bool:
        """Verify Redis server connectivity."""
        try:
            client = self._get_client()
            ping_res = bool(client.ping())
            if ping_res:
                connection_info = settings.REDIS_URL if settings.REDIS_URL else f"{settings.REDIS_HOST}:{settings.REDIS_PORT}"
                if "@" in connection_info:
                    try:
                        prefix, rest = connection_info.split("://", 1)
                        creds, host_part = rest.split("@", 1)
                        connection_info = f"{prefix}://***@{host_part}"
                    except Exception:
                        connection_info = "Cloud Redis URL"
                logger.info(f"Redis Connected successfully to {connection_info}")
            return ping_res
        except Exception as exc:
            logger.error(f"Failed to connect to Redis server: {str(exc)}")
            return False

    def enqueue_job(self, payload: JobQueuePayload, priority: bool = False) -> int:
        """Enqueue a bulk enrichment job payload into Redis queue (FIFO or Priority list)."""
        start_time = time.perf_counter()
        if not isinstance(payload, JobQueuePayload):
            raise ValidationException("Invalid queue payload type provided")

        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is None:
            if any(p.job_id == payload.job_id for p in self._in_memory_queue):
                raise DuplicateRecordException(f"Job with ID '{payload.job_id}' is already queued")
            if priority:
                self._in_memory_queue.insert(0, payload)
            else:
                self._in_memory_queue.append(payload)
            return len(self._in_memory_queue)

        # Step 1: Check for duplicate job queuing
        try:
            existing_items = client.lrange(self._queue_name, 0, -1)
            for item in existing_items:
                try:
                    data = json.loads(item)
                    if data.get("job_id") == payload.job_id:
                        logger.warning(f"Duplicate queue request rejected for job_id '{payload.job_id}'")
                        raise DuplicateRecordException(
                            message=f"Job with ID '{payload.job_id}' is already queued",
                            details={"job_id": payload.job_id},
                        )
                except (json.JSONDecodeError, TypeError):
                    continue
        except (redis.ConnectionError, redis.TimeoutError) as conn_err:
            logger.error(f"Redis Connection Error during duplicate check: {str(conn_err)}")
            raise APIException(
                message=f"Redis service unavailable: {str(conn_err)}",
                status_code=503,
                details={"error": str(conn_err)},
            )
        except DuplicateRecordException:
            raise
        except Exception as exc:
            logger.error(f"Unexpected Redis error during duplicate check: {str(exc)}")

        # Step 2: Serialize payload to JSON
        try:
            json_payload = payload.model_dump_json()
        except Exception as exc:
            logger.error(f"Serialization error for job_id '{payload.job_id}': {str(exc)}")
            raise ValidationException(f"Failed to serialize job queue payload: {str(exc)}")

        # Step 3: Push payload to Redis queue (LPUSH if priority else RPUSH)
        try:
            if priority:
                queue_len = client.lpush(self._queue_name, json_payload)
            else:
                queue_len = client.rpush(self._queue_name, json_payload)

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                f"Job Queued: job_id='{payload.job_id}' (Priority={priority}) to queue='{self._queue_name}' "
                f"| Queue position={queue_len} | Execution time={duration_ms}ms"
            )
            return queue_len
        except (redis.ConnectionError, redis.TimeoutError, redis.AuthenticationError) as redis_err:
            logger.error(f"Redis Queue Failure for job '{payload.job_id}': {str(redis_err)}")
            raise APIException(
                message=f"Failed to enqueue job due to Redis connection failure: {str(redis_err)}",
                status_code=503,
                details={"job_id": payload.job_id, "error": str(redis_err)},
            )
        except Exception as exc:
            logger.error(f"Unexpected error while pushing job '{payload.job_id}' to Redis: {str(exc)}")
            raise DatabaseException(
                message=f"Redis error pushing job to queue: {str(exc)}",
                details={"job_id": payload.job_id, "error": str(exc)},
            )

    def dequeue_job(self) -> Optional[JobQueuePayload]:
        """Pop next available job payload from front of Redis queue (LPOP)."""
        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is None:
            if self._in_memory_queue:
                return self._in_memory_queue.pop(0)
            return None

        try:
            raw_data = client.lpop(self._queue_name)
            if not raw_data:
                return None
            return JobQueuePayload.model_validate_json(raw_data)
        except Exception as exc:
            logger.error(f"Failed to dequeue job payload from Redis: {str(exc)}")
            if self._in_memory_queue:
                return self._in_memory_queue.pop(0)
            return None

    def peek_queue(self, limit: int = 10) -> List[JobQueuePayload]:
        """Retrieve upcoming queued jobs without removing them from Redis."""
        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is None:
            return self._in_memory_queue[:limit]

        try:
            raw_items = client.lrange(self._queue_name, 0, limit - 1)
            queued_jobs: List[JobQueuePayload] = []
            for item in raw_items:
                try:
                    queued_jobs.append(JobQueuePayload.model_validate_json(item))
                except Exception as parse_err:
                    logger.warning(f"Skipping malformed queue payload: {str(parse_err)}")
                    continue
            return queued_jobs
        except Exception as exc:
            logger.error(f"Failed to peek Redis queue: {str(exc)}")
            return self._in_memory_queue[:limit]

    def get_queue_size(self) -> int:
        """Get current total size (number of pending jobs) in Redis queue."""
        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is None:
            return len(self._in_memory_queue)

        try:
            size = client.llen(self._queue_name)
            return size
        except Exception as exc:
            logger.warning(f"Could not fetch Redis queue size: {str(exc)}")
            return len(self._in_memory_queue)

    def get_queue_length(self) -> int:
        """Alias for get_queue_size()."""
        return self.get_queue_size()

    def remove_job(self, job_id: str) -> bool:
        """Remove a specific job payload by job_id from Redis queue."""
        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is None:
            for idx, p in enumerate(self._in_memory_queue):
                if p.job_id == job_id:
                    self._in_memory_queue.pop(idx)
                    return True
            return False

        try:
            raw_items = client.lrange(self._queue_name, 0, -1)
            for item in raw_items:
                try:
                    data = json.loads(item)
                    if data.get("job_id") == job_id:
                        removed_count = client.lrem(self._queue_name, 1, item)
                        if removed_count > 0:
                            logger.info(f"Removed job '{job_id}' from Redis queue '{self._queue_name}'")
                            return True
                except (json.JSONDecodeError, TypeError):
                    continue
            return False
        except Exception as exc:
            logger.error(f"Error removing job '{job_id}' from Redis queue: {str(exc)}")
            return False

    def register_worker_heartbeat(
        self,
        worker_id: str,
        current_job_id: Optional[str] = None,
        processed_count: int = 0,
        worker_status: str = "IDLE",
    ) -> None:
        """Register worker heartbeat in Redis hash or memory store."""
        hb_data = {
            "worker_id": worker_id,
            "last_seen": time.time(),
            "current_job_id": current_job_id or "",
            "processed_count": processed_count,
            "status": worker_status,
        }
        hb_key = f"worker:heartbeat:{worker_id}"

        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is not None:
            try:
                client.hset(hb_key, mapping=hb_data)
                client.expire(hb_key, 30)
                return
            except Exception as exc:
                logger.warning(f"Failed to record Redis heartbeat for worker '{worker_id}': {str(exc)}")

        self._in_memory_heartbeats[worker_id] = hb_data

    def get_active_workers(self) -> List[Dict[str, Any]]:
        """Retrieve list of active workers registered via heartbeat."""
        now = time.time()
        active: List[Dict[str, Any]] = []

        client = None
        try:
            client = self._get_client()
        except Exception:
            client = None

        if client is not None:
            try:
                keys = client.keys("worker:heartbeat:*")
                for k in keys:
                    data = client.hgetall(k)
                    if data and (now - float(data.get("last_seen", 0))) <= 30:
                        active.append(data)
                return active
            except Exception as exc:
                logger.warning(f"Error listing Redis worker heartbeats: {str(exc)}")

        for w_id, hb in list(self._in_memory_heartbeats.items()):
            if (now - hb.get("last_seen", 0)) <= 30:
                active.append(hb)
        return active

    def health_check(self) -> RedisHealthStatus:
        """Perform Redis health check via RedisHealthService."""
        return self._health_service.check_health()

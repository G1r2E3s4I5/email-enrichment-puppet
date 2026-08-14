"""DistributedLockService providing safe, atomic, Redis-backed distributed locking with Lua scripts and in-memory fallback."""

import time
from typing import Dict, Optional, Tuple
import redis

from app.config.logging import logger


class DistributedLockService:
    """Production distributed locking engine ensuring single-ownership of concurrent jobs across multiple workers."""

    _shared_memory_locks: Dict[str, Tuple[str, float]] = {}

    def __init__(self, redis_client: Optional[redis.Redis] = None) -> None:
        """Initialize service with injected Redis client or fallback memory store."""
        self._client = redis_client

    def _get_client(self) -> Optional[redis.Redis]:
        """Retrieve client or singleton."""
        if self._client is not None:
            return self._client
        try:
            from app.api.dependencies.services import get_redis_client
            return get_redis_client()
        except Exception:
            return None

    def acquire_lock(self, lock_key: str, owner_id: str, ttl_sec: int = 300) -> bool:
        """Acquire atomic distributed lock for lock_key with specified owner_id and TTL."""
        full_key = f"lock:{lock_key}" if not lock_key.startswith("lock:") else lock_key
        client = self._get_client()

        if client is not None:
            try:
                acquired = bool(client.set(full_key, owner_id, nx=True, ex=ttl_sec))
                if acquired:
                    logger.info(f"[DistributedLock]: Lock '{full_key}' acquired by owner '{owner_id}' (TTL: {ttl_sec}s)")
                else:
                    logger.debug(f"[DistributedLock]: Failed to acquire '{full_key}' — already locked by another owner")
                return acquired
            except Exception as exc:
                logger.warning(f"[DistributedLock]: Redis lock acquisition error for '{full_key}': {str(exc)}. Falling back to memory lock.")

        # Fallback memory lock
        now = time.time()
        existing = self._shared_memory_locks.get(full_key)
        if existing and existing[1] > now:
            if existing[0] == owner_id:
                # Re-entrant / extend
                self._shared_memory_locks[full_key] = (owner_id, now + ttl_sec)
                return True
            return False

        self._shared_memory_locks[full_key] = (owner_id, now + ttl_sec)
        logger.info(f"[DistributedLock Memory]: Lock '{full_key}' acquired by owner '{owner_id}'")
        return True

    def release_lock(self, lock_key: str, owner_id: str) -> bool:
        """Safely release distributed lock using atomic Lua script checking owner identity."""
        full_key = f"lock:{lock_key}" if not lock_key.startswith("lock:") else lock_key
        client = self._get_client()

        if client is not None:
            lua_release = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                result = client.eval(lua_release, 1, full_key, owner_id)
                released = bool(result)
                if released:
                    logger.info(f"[DistributedLock]: Released lock '{full_key}' by owner '{owner_id}'")
                return released
            except Exception as exc:
                logger.warning(f"[DistributedLock]: Redis lock release error for '{full_key}': {str(exc)}")

        existing = self._shared_memory_locks.get(full_key)
        if existing and existing[0] == owner_id:
            del self._shared_memory_locks[full_key]
            logger.info(f"[DistributedLock Memory]: Released lock '{full_key}' by owner '{owner_id}'")
            return True
        return False

    def renew_lock(self, lock_key: str, owner_id: str, ttl_sec: int = 300) -> bool:
        """Renew TTL for an active lock owned by owner_id."""
        full_key = f"lock:{lock_key}" if not lock_key.startswith("lock:") else lock_key
        client = self._get_client()

        if client is not None:
            lua_renew = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            try:
                result = client.eval(lua_renew, 1, full_key, owner_id, str(ttl_sec))
                renewed = bool(result)
                if renewed:
                    logger.debug(f"[DistributedLock]: Renewed lock '{full_key}' for owner '{owner_id}' (+{ttl_sec}s)")
                return renewed
            except Exception as exc:
                logger.warning(f"[DistributedLock]: Lock renewal error for '{full_key}': {str(exc)}")

        existing = self._shared_memory_locks.get(full_key)
        if existing and existing[0] == owner_id:
            self._shared_memory_locks[full_key] = (owner_id, time.time() + ttl_sec)
            return True
        return False

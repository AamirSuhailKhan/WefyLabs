"""
WefyLabs Distributed Redis Lock & Celery Beat Safety
====================================================
Atomic distributed locking using Redis SET NX EX with Lua release script.
Guarantees:
- Safe singleton execution of periodic Celery Beat tasks across multi-worker clusters.
- Automatic expiration via TTL to prevent stale deadlocks.
- Random token verification during release: prevents releasing locks acquired by subsequent workers.
- Graceful in-memory fallback when Redis is offline.
"""
from __future__ import annotations

import functools
import logging
import time
import uuid
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, Generator, AsyncGenerator, Callable, Any

logger = logging.getLogger("wefylabs.redis.lock")

# Lua script to release lock only if the token matches
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

# In-memory lock fallback when Redis is unreachable
_in_memory_locks: dict[str, tuple[str, float]] = {}


def _get_redis_sync():
    """Retrieves sync redis client via rate_limiter's pooled connector."""
    from app.common.redis.rate_limiter import _get_redis
    return _get_redis()


class RedisDistributedLock:
    """
    Atomic Redis Distributed Lock manager.
    """

    @classmethod
    def acquire(
        cls,
        lock_name: str,
        ttl_seconds: int = 60,
        fail_closed: bool = False
    ) -> tuple[bool, Optional[str]]:
        """
        Attempts to acquire a distributed lock.
        Returns (acquired: bool, token: Optional[str]).
        """
        token = str(uuid.uuid4())
        key = f"lock:{lock_name}"
        redis_client = _get_redis_sync()

        if redis_client is not None:
            try:
                acquired = redis_client.set(key, token, nx=True, ex=ttl_seconds)
                if acquired:
                    logger.debug(f"[RedisLock] Acquired '{lock_name}' (ttl={ttl_seconds}s)")
                    return True, token
                else:
                    logger.debug(f"[RedisLock] Could not acquire '{lock_name}' — already held")
                    return False, None
            except Exception as exc:
                logger.warning(f"[RedisLock] Redis error acquiring '{lock_name}': {exc}")
                if fail_closed:
                    return False, None

        # In-memory fallback
        now = time.time()
        # Clean expired
        if key in _in_memory_locks:
            _, expiry = _in_memory_locks[key]
            if now >= expiry:
                del _in_memory_locks[key]

        if key not in _in_memory_locks:
            _in_memory_locks[key] = (token, now + ttl_seconds)
            logger.debug(f"[RedisLock Fallback] Acquired in-memory '{lock_name}'")
            return True, token
        return False, None

    @classmethod
    def release(cls, lock_name: str, token: Optional[str]) -> bool:
        """
        Releases the distributed lock using atomic token comparison.
        """
        if not token:
            return False

        key = f"lock:{lock_name}"
        redis_client = _get_redis_sync()

        if redis_client is not None:
            try:
                res = redis_client.eval(_RELEASE_LUA, 1, key, token)
                return bool(res)
            except Exception as exc:
                logger.warning(f"[RedisLock] Redis error releasing '{lock_name}': {exc}")

        # In-memory release
        if key in _in_memory_locks:
            current_token, _ = _in_memory_locks[key]
            if current_token == token:
                del _in_memory_locks[key]
                return True
        return False


@contextmanager
def distributed_lock(
    lock_name: str,
    ttl_seconds: int = 60,
    fail_closed: bool = False
) -> Generator[bool, None, None]:
    """
    Synchronous context manager for distributed locking.
    Yields True if lock was acquired, False otherwise.
    """
    acquired, token = RedisDistributedLock.acquire(
        lock_name,
        ttl_seconds=ttl_seconds,
        fail_closed=fail_closed
    )
    try:
        yield acquired
    finally:
        if acquired:
            RedisDistributedLock.release(lock_name, token)


@asynccontextmanager
async def async_distributed_lock(
    lock_name: str,
    ttl_seconds: int = 60,
    fail_closed: bool = False
) -> AsyncGenerator[bool, None]:
    """
    Async context manager for distributed locking.
    """
    acquired, token = RedisDistributedLock.acquire(
        lock_name,
        ttl_seconds=ttl_seconds,
        fail_closed=fail_closed
    )
    try:
        yield acquired
    finally:
        if acquired:
            RedisDistributedLock.release(lock_name, token)


def singleton_periodic_task(
    lock_name: Optional[str] = None,
    ttl_seconds: int = 60
):
    """
    Celery task decorator that guarantees only one worker executes a periodic task
    across all nodes in the cluster. If lock is already held, exits gracefully.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            actual_lock = lock_name or f"celery:task:{func.__name__}"
            with distributed_lock(actual_lock, ttl_seconds=ttl_seconds) as acquired:
                if not acquired:
                    logger.info(
                        f"[SingletonTask] Skipping {func.__name__} — another worker holds lock '{actual_lock}'"
                    )
                    return {"skipped": True, "reason": "lock_held", "task": func.__name__}
                return func(*args, **kwargs)
        return wrapper
    return decorator

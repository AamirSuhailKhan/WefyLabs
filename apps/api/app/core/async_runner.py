"""
Centralized Persistent Event Loop and Async Task Runner for Celery Workers
========================================================================
Solves the SQLAlchemy / asyncpg / Celery event loop lifecycle problem:
1. Maintains a persistent, open event loop per worker process / thread via threading.local.
2. Does NOT close the loop after running coroutines, preventing pooled
   asyncpg connections from becoming attached to a closed event loop.
3. Automatically disposes the SQLAlchemy engine connection pool if an event
   loop is ever replaced or closed, preventing checkout of stranded connections.
4. Provides lifecycle hooks for Celery worker_process_init and worker_process_shutdown.
"""

import asyncio
import logging
import threading
from typing import Any, Coroutine, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Thread-local storage to provide thread-isolated persistent event loops
_local = threading.local()


def get_worker_event_loop() -> asyncio.AbstractEventLoop:
    """
    Returns an open, active event loop for the current process/thread.
    If no loop exists or if the current loop was closed, creates a new one
    and disposes any stale connections in the SQLAlchemy pool.
    """
    loop = getattr(_local, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _local.loop = loop
        _dispose_engine_pool()
    return loop


def _dispose_engine_pool() -> None:
    """Safely disposes SQLAlchemy's underlying engine pool to drop stale connections."""
    try:
        from app.database import engine
        if hasattr(engine, "sync_engine"):
            engine.sync_engine.dispose()
    except Exception as exc:
        logger.debug(f"[AsyncRunner] Engine pool disposal notice: {exc}")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Runs an asynchronous coroutine synchronously using the persistent loop.
    Does NOT close the loop after execution, preserving connection pool state.
    """
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is not None and running_loop.is_running():
        # Already inside an active running loop (e.g. during async tests)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()

    loop = get_worker_event_loop()
    return loop.run_until_complete(coro)


def reset_worker_event_loop() -> None:
    """
    Called upon worker process initialization (e.g., Celery fork).
    Clears any inherited loop and disposes inherited database connection pools.
    """
    _dispose_engine_pool()
    loop = getattr(_local, "loop", None)
    if loop is not None and not loop.is_closed():
        try:
            loop.close()
        except Exception:
            pass
    _local.loop = None


def close_worker_event_loop() -> None:
    """
    Called upon worker process shutdown.
    Disposes engine pool and closes the worker event loop.
    """
    _dispose_engine_pool()
    loop = getattr(_local, "loop", None)
    if loop is not None and not loop.is_closed():
        try:
            loop.close()
        except Exception:
            pass
    _local.loop = None

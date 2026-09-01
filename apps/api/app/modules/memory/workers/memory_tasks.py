"""
Celery Background Tasks for AI Memory & Customer Intelligence Engine
====================================================================
Executes periodic asynchronous maintenance jobs:
- Evaluating memory recency decay curves (daily)
- Enforcing memory retention policy TTL cleanup
"""

import asyncio
import logging
from typing import List, Dict, Any

from app.celery_app import celery_app
from app.database import async_session_factory
from app.modules.memory.service import AIMemoryService

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Helper to run async coroutines synchronously in Celery worker thread."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.modules.memory.workers.memory_tasks.evaluate_memory_decay_task", queue="memory-decay")
def evaluate_memory_decay_task():
    """Evaluates memory records exceeding their half-life and marks them STALE (daily)."""
    async def _runner():
        async with async_session_factory() as session:
            logger.info("[MEMORY_TASK] Evaluating memory decay across active records...")
            service = AIMemoryService(session)
            stale_records = await service.evaluate_memory_decay()
            logger.info(f"[MEMORY_TASK] Evaluated decay; marked {len(stale_records)} record(s) STALE.")
            return {"status": "SUCCESS", "stale_count": len(stale_records)}

    return _run_async(_runner())
